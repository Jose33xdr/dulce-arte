"""
Administración avanzada para el módulo de Clientes en Dulce Arte.
"""

from django.contrib import admin
from django.utils.html import format_html
from .models import Client


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    """Gestión administrativa de clientes con auditoría y desactivación lógica."""

    list_display = (
        "identification",
        "name",
        "phone",
        "email",
        "active_badge",
        "created_at",
    )
    list_filter = ("is_active", "created_at")
    search_fields = ("identification", "name", "phone", "email", "address")
    readonly_fields = ("created_at", "updated_at", "deleted_at")
    ordering = ["name"]

    fieldsets = (
        (
            "Identificación del Cliente",
            {
                "fields": ("identification", "name", "is_active"),
            },
        ),
        (
            "Datos de Contacto y Despacho",
            {
                "fields": ("phone", "email", "address"),
            },
        ),
        (
            "Notas Especiales",
            {
                "fields": ("notes",),
            },
        ),
        (
            "Metadatos y Auditoría",
            {
                "classes": ("collapse",),
                "fields": ("created_at", "updated_at", "deleted_at"),
            },
        ),
    )

    @admin.display(description="Estado")
    def active_badge(self, obj):
        if obj.is_active:
            return format_html(
                '<span style="background-color: #DCEBDD; color: #2d5a33; padding: 3px 8px; border-radius: 9999px; font-weight: bold; font-size: 11px;">Activo</span>'
            )
        return format_html(
            '<span style="background-color: #FEE2E2; color: #991B1B; padding: 3px 8px; border-radius: 9999px; font-weight: bold; font-size: 11px;">Desactivado</span>'
        )

    actions = ["soft_delete_clients", "restore_clients"]

    @admin.action(description="Desactivar clientes seleccionados (Eliminación lógica protegida)")
    def soft_delete_clients(self, request, queryset):
        for client in queryset:
            client.soft_delete()
        self.message_user(request, f"{queryset.count()} cliente(s) desactivado(s) exitosamente.")

    @admin.action(description="Reactivar clientes seleccionados")
    def restore_clients(self, request, queryset):
        for client in queryset:
            client.restore()
        self.message_user(request, f"{queryset.count()} cliente(s) reactivado(s) exitosamente.")
