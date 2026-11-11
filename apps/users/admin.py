"""
Configuración de administración para el modelo de usuario personalizado.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Administración personalizada del usuario institucional Dulce Arte."""

    list_display = (
        "username",
        "email",
        "role",
        "identification",
        "phone",
        "is_staff",
        "is_active",
    )
    list_filter = ("role", "is_staff", "is_superuser", "is_active")
    search_fields = ("username", "first_name", "last_name", "email", "identification")
    ordering = ("username",)

    fieldsets = BaseUserAdmin.fieldsets + (
        (
            "Información Operativa Dulce Arte",
            {
                "fields": ("role", "identification", "phone"),
            },
        ),
    )

    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        (
            "Información Operativa Dulce Arte",
            {
                "classes": ("wide",),
                "fields": ("role", "identification", "phone"),
            },
        ),
    )
