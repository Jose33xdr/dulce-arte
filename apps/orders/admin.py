"""
Administración avanzada para Pedidos, Cotizaciones y Personalizaciones en Dulce Arte.
Incluye inlines tabulares de ítems, historial de estados de solo lectura y badges visuales.
"""

from django.contrib import admin
from django.utils.html import format_html
from .models import DeliveryType, Order, OrderItem, OrderStatus, OrderStatusHistory


class OrderItemInline(admin.TabularInline):
    """Ítems de pastelería personalizada incluidos en el pedido."""

    model = OrderItem
    extra = 0
    autocomplete_fields = ["product"]
    fields = (
        "product",
        "quantity",
        "unit_price",
        "subtotal",
        "cake_size",
        "flavor_sponge",
        "flavor_filling",
        "flavor_cover",
        "custom_dedication",
    )


class OrderStatusHistoryInline(admin.TabularInline):
    """Historial inmutable de estados de un pedido."""

    model = OrderStatusHistory
    extra = 0
    readonly_fields = ("previous_status", "new_status", "changed_by", "reason", "created_at")
    can_delete = False
    ordering = ["-created_at"]

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "order_number",
        "client",
        "delivery_date",
        "delivery_time",
        "delivery_type_badge",
        "total_amount",
        "deposit_amount",
        "balance_due",
        "status_badge",
    )
    list_filter = ("status", "delivery_type", "delivery_date")
    search_fields = (
        "order_number",
        "client__name",
        "client__identification",
        "delivery_address",
    )
    readonly_fields = ("order_number", "balance_due", "created_at", "updated_at")
    ordering = ["-delivery_date", "-delivery_time"]
    list_select_related = ("client",)
    inlines = [OrderItemInline, OrderStatusHistoryInline]

    fieldsets = (
        (
            "Identificación del Pedido",
            {
                "fields": ("order_number", "client", "status"),
            },
        ),
        (
            "Programación de Entrega",
            {
                "fields": ("delivery_date", "delivery_time", "delivery_type", "delivery_address"),
            },
        ),
        (
            "Balance Financiero ($)",
            {
                "fields": ("total_amount", "deposit_amount", "balance_due"),
            },
        ),
        (
            "Diseño Artesanal y Referencias",
            {
                "fields": ("custom_design_notes", "reference_image"),
            },
        ),
        (
            "Auditoría",
            {
                "classes": ("collapse",),
                "fields": ("created_at", "updated_at"),
            },
        ),
    )

    @admin.display(description="Estado Comercial")
    def status_badge(self, obj):
        colores = {
            OrderStatus.COTIZACION: ("#E0E7FF", "#3730A3"),
            OrderStatus.CONFIRMADO: ("#DCEBDD", "#2d5a33"),
            OrderStatus.EN_PRODUCCION: ("#FEF3C7", "#92400E"),
            OrderStatus.LISTO: ("#F3D6DB", "#773344"),
            OrderStatus.EN_DESPACHO: ("#CFFAFE", "#155E75"),
            OrderStatus.ENTREGADO: ("#D1FAE5", "#065F46"),
            OrderStatus.CANCELADO: ("#FEE2E2", "#991B1B"),
        }
        bg, text = colores.get(obj.status, ("#F3F4F6", "#374151"))
        return format_html(
            f'<span style="background-color: {bg}; color: {text}; padding: 3px 8px; border-radius: 9999px; font-weight: bold; font-size: 11px;">{obj.get_status_display()}</span>'
        )

    @admin.display(description="Tipo Entrega")
    def delivery_type_badge(self, obj):
        if obj.delivery_type == DeliveryType.DESPACHO_DOMICILIO:
            return format_html(
                '<span style="color: #773344; font-weight: 600; font-size: 11px;">🚚 Domicilio</span>'
            )
        return format_html(
            '<span style="color: #4B5563; font-weight: 600; font-size: 11px;">🏪 Tienda</span>'
        )


@admin.register(OrderStatusHistory)
class OrderStatusHistoryAdmin(admin.ModelAdmin):
    list_display = ("order", "previous_status", "new_status", "changed_by", "created_at")
    list_filter = ("new_status", "created_at")
    search_fields = ("order__order_number", "changed_by__username", "reason")
    readonly_fields = ("order", "previous_status", "new_status", "changed_by", "reason", "created_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
