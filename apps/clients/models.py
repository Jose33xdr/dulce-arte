"""
Modelos de dominio para clientes de Dulce Arte.
Soporta identificación única (RUT/DNI) y desactivación lógica protegida.
"""

from django.db import models
from apps.core.models import SoftDeleteModel
from apps.core.validators import validate_rut_or_dni, clean_rut


class Client(SoftDeleteModel):
    """
    Cliente de la pastelería artesanal Dulce Arte.
    Soporta pedidos directos, cotizaciones y entregas a domicilio.
    """

    identification = models.CharField(
        max_length=20,
        unique=True,
        db_index=True,
        validators=[validate_rut_or_dni],
        verbose_name="RUT / DNI",
        help_text="Identificación única del cliente (ej. 12.345.678-5 o pasaporte).",
    )
    name = models.CharField(
        max_length=150,
        verbose_name="Nombre completo",
        help_text="Nombre y apellidos del cliente o razón social.",
    )
    email = models.EmailField(
        max_length=120,
        blank=True,
        verbose_name="Correo electrónico",
        help_text="Correo de contacto para notificaciones y cotizaciones.",
    )
    phone = models.CharField(
        max_length=25,
        blank=True,
        verbose_name="Teléfono",
        help_text="Teléfono o WhatsApp de contacto.",
    )
    address = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Dirección principal",
        help_text="Dirección predeterminada para entregas y despacho.",
    )
    notes = models.TextField(
        blank=True,
        verbose_name="Observaciones",
        help_text="Preferencias de empaque, alergias del cliente, etc.",
    )

    class Meta:
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["identification"], name="idx_client_identification"),
            models.Index(fields=["name"], name="idx_client_name"),
        ]

    def clean(self):
        super().clean()
        if self.identification:
            # Normalizar guardando sin puntos ni guiones para unicidad limpia
            cleaned = clean_rut(self.identification)
            if len(cleaned) >= 7 and cleaned[:-1].isdigit():
                # Formatear estándar: 12345678-K
                self.identification = f"{cleaned[:-1]}-{cleaned[-1]}"
            else:
                self.identification = cleaned

    def __str__(self):
        return f"{self.name} ({self.identification})"
