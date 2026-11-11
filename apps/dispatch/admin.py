"""
Administración avanzada para Rutas de Despacho, Paradas y Comprobantes de Entrega en Dulce Arte.
Permite gestionar la secuencia de paradas en ruta y auditar la recepción de pedidos.
"""

from django.contrib import admin
from django.utils.html import format_html
from .models import DeliveryProof, DeliveryRoute, DispatchOrder, DispatchStatus, RouteStatus


class DispatchOrderInline(admin.TabularInline):
    """Paradas ordenadas vinculadas a la ruta de entrega."""

    model = DispatchOrder
    extra = 0
    fields = ("stop_order", "order", "status", "assigned_driver", "delivered_at")
    ordering = ["stop_order"]


@admin.register(DeliveryRoute)
class DeliveryRouteAdmin(admin.ModelAdmin):
    list_display = ("code", "assigned_driver", "scheduled_date", "status_badge", "stops_count")
    list_filter = ("status", "scheduled_date")
    search_fields = ("code", "assigned_driver__username", "notes")
    inlines = [DispatchOrderInline]
    ordering = ["-scheduled_date", "code"]
    list_select_related = ("assigned_driver",)

    @admin.display(description="Estado de Ruta")
    def status_badge(self, obj):
        colores = {
            RouteStatus.PROGRAMADA: ("#E0E7FF", "#3730A3"),
            RouteStatus.EN_CURSO: ("#FEF3C7", "#92400E"),
            RouteStatus.COMPLETADA: ("#DCEBDD", "#2d5a33"),
            RouteStatus.CANCELADA: ("#FEE2E2", "#991B1B"),
        }
        bg, text = colores.get(obj.status, ("#F3F4F6", "#374151"))
        return format_html(
            f'<span style="background-color: {bg}; color: {text}; padding: 3px 8px; border-radius: 9999px; font-weight: bold; font-size: 11px;">{obj.get_status_display()}</span>'
        )

    @admin.display(description="Total Paradas")
    def stops_count(self, obj):
        return obj.dispatches.count()


@admin.register(DispatchOrder)
class DispatchOrderAdmin(admin.ModelAdmin):
    list_display = (
        "order",
        "route",
        "stop_order",
        "assigned_driver",
        "status_badge",
        "has_proof_badge",
        "dispatched_at",
        "delivered_at",
    )
    list_filter = ("status", "route__scheduled_date")
    search_fields = (
        "order__order_number",
        "assigned_driver__username",
        "route__code",
        "order__client__name",
    )
    ordering = ["route", "stop_order", "-created_at"]
    list_select_related = ("order", "route", "assigned_driver")

    @admin.display(description="Estado Despacho")
    def status_badge(self, obj):
        colores = {
            DispatchStatus.PENDIENTE: ("#E0E7FF", "#3730A3"),
            DispatchStatus.EN_RUTA: ("#FEF3C7", "#92400E"),
            DispatchStatus.ENTREGADO: ("#DCEBDD", "#2d5a33"),
            DispatchStatus.FALLIDO: ("#FEE2E2", "#991B1B"),
        }
        bg, text = colores.get(obj.status, ("#F3F4F6", "#374151"))
        return format_html(
            f'<span style="background-color: {bg}; color: {text}; padding: 3px 8px; border-radius: 9999px; font-weight: bold; font-size: 11px;">{obj.get_status_display()}</span>'
        )

    @admin.display(description="Certificación")
    def has_proof_badge(self, obj):
        if hasattr(obj, "proof") and obj.proof:
            return format_html(
                '<span style="color: #2d5a33; font-weight: bold; font-size: 11px;">✓ Firmado</span>'
            )
        return format_html(
            '<span style="color: #9CA3AF; font-size: 11px;">Pendiente</span>'
        )


@admin.register(DeliveryProof)
class DeliveryProofAdmin(admin.ModelAdmin):
    list_display = ("dispatch_order", "recipient_name", "recipient_id", "registered_at")
    search_fields = ("dispatch_order__order__order_number", "recipient_name", "recipient_id")
    readonly_fields = (
        "dispatch_order",
        "recipient_name",
        "recipient_id",
        "signature_data",
        "proof_photo",
        "registered_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
