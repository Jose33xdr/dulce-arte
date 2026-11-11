"""
Modelo de usuario personalizado para Dulce Arte con roles RBAC integrados.
"""

import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models


class UserRole(models.TextChoices):
    ADMIN = "ADMIN", "Administrador"
    VENTAS = "VENTAS", "Ventas y Atención"
    COCINA = "COCINA", "Cocina y Pastelería"
    REPARTIDOR = "REPARTIDOR", "Repartidor y Despacho"


class User(AbstractUser):
    """
    Usuario personalizado para el sistema Dulce Arte.
    Sustituye al modelo de usuario por defecto de Django y añade rol específico.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    role = models.CharField(
        max_length=20,
        choices=UserRole.choices,
        default=UserRole.VENTAS,
        verbose_name="Rol en el sistema",
        help_text="Define los permisos y accesos operativos del usuario.",
    )
    phone = models.CharField(
        max_length=20,
        blank=True,
        verbose_name="Teléfono de contacto",
    )
    identification = models.CharField(
        max_length=20,
        blank=True,
        verbose_name="RUT / DNI",
        help_text="Documento de identidad del colaborador.",
    )

    class Meta:
        verbose_name = "Usuario"
        verbose_name_plural = "Usuarios"
        ordering = ["username"]

    def __str__(self):
        full = self.get_full_name()
        display_name = full if full else self.username
        return f"{display_name} ({self.get_role_display()})"

    @property
    def is_admin(self) -> bool:
        return self.is_superuser or self.role == UserRole.ADMIN

    @property
    def is_sales(self) -> bool:
        return self.role == UserRole.VENTAS or self.is_admin

    @property
    def is_kitchen(self) -> bool:
        return self.role == UserRole.COCINA or self.is_admin

    @property
    def is_delivery(self) -> bool:
        return self.role == UserRole.REPARTIDOR or self.is_admin
