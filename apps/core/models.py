"""
Modelos base y utilidades abstractas para Dulce Arte.
Aportan trazabilidad temporal y soporte para eliminación protegida/lógica.
"""

import uuid
from django.db import models
from django.utils import timezone


class TimeStampedModel(models.Model):
    """
    Modelo base abstracto que añade marcas de tiempo automáticas para
    creación y última modificación.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de creación",
        help_text="Fecha y hora de creación del registro",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Fecha de modificación",
        help_text="Fecha y hora de última modificación",
    )

    class Meta:
        abstract = True
        ordering = ["-created_at"]


class SoftDeleteModel(TimeStampedModel):
    """
    Modelo abstracto para entidades con desactivación/eliminación lógica protegida.
    Garantiza que ningún registro con historial sea eliminado físicamente de la base de datos.
    """

    is_active = models.BooleanField(
        default=True,
        verbose_name="Activo",
        help_text="Indica si el registro está operativo o desactivado.",
    )
    deleted_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Fecha de eliminación",
        help_text="Fecha y hora en que se desactivó el registro.",
    )

    class Meta:
        abstract = True

    def soft_delete(self):
        """Desactiva lógicamente el registro conservando integridad referencial."""
        self.is_active = False
        self.deleted_at = timezone.now()
        self.save(update_fields=["is_active", "deleted_at"])

    def restore(self):
        """Restaura un registro desactivado."""
        self.is_active = True
        self.deleted_at = None
        self.save(update_fields=["is_active", "deleted_at"])
