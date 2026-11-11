"""
Administración avanzada para Insumos, Unidades de Medida y Movimientos de Stock en Dulce Arte.
Protege el historial inmutable de movimientos y destaca visualmente alertas de inventario.
"""

from django.contrib import admin
from django.utils.html import format_html
from .models import MovementType, StockMovement, Supply, UnitOfMeasure


@admin.register(UnitOfMeasure)
class UnitOfMeasureAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "magnitude", "conversion_factor", "is_active")
    list_filter = ("magnitude", "is_active")
    search_fields = ("code", "name")
    ordering = ["magnitude", "code"]


@admin.register(Supply)
class SupplyAdmin(admin.ModelAdmin):
    list_display = (
        "sku",
        "name",
        "unit_of_measure",
        "current_stock",
        "minimum_stock",
        "cost_per_unit",
        "stock_status_badge",
        "is_active",
    )
    list_filter = ("unit_of_measure__magnitude", "is_active")
    search_fields = ("sku", "name")
    readonly_fields = ("created_at", "updated_at", "deleted_at")
    ordering = ["name"]
    list_select_related = ("unit_of_measure",)

    fieldsets = (
        (
            "Identificación del Insumo",
            {
                "fields": ("sku", "name", "unit_of_measure", "is_active"),
            },
        ),
        (
            "Control de Existencias y Costos",
            {
                "fields": ("current_stock", "minimum_stock", "cost_per_unit"),
            },
        ),
        (
            "Auditoría",
            {
                "classes": ("collapse",),
                "fields": ("created_at", "updated_at", "deleted_at"),
            },
        ),
    )

    @admin.display(description="Estado de Stock")
    def stock_status_badge(self, obj):
        if obj.is_low_stock:
            return format_html(
                '<span style="background-color: #FEE2E2; color: #991B1B; padding: 3px 8px; border-radius: 9999px; font-weight: bold; font-size: 11px;">⚠️ Stock Crítico</span>'
            )
        return format_html(
            '<span style="background-color: #DCEBDD; color: #2d5a33; padding: 3px 8px; border-radius: 9999px; font-weight: bold; font-size: 11px;">✓ Óptimo</span>'
        )


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    """
    Administración de solo lectura para preservar la trazabilidad inmutable de movimientos.
    """

    list_display = (
        "created_at",
        "supply",
        "movement_badge",
        "quantity",
        "stock_before",
        "stock_after",
        "user",
        "reference",
    )
    list_filter = ("movement_type", "created_at")
    search_fields = ("supply__name", "supply__sku", "reference", "user__username")
    readonly_fields = (
        "id",
        "supply",
        "movement_type",
        "quantity",
        "stock_before",
        "stock_after",
        "user",
        "reference",
        "notes",
        "created_at",
        "updated_at",
    )
    ordering = ["-created_at"]
    list_select_related = ("supply", "supply__unit_of_measure", "user")

    @admin.display(description="Tipo Movimiento")
    def movement_badge(self, obj):
        colores = {
            MovementType.ENTRADA: ("#DCEBDD", "#2d5a33"),
            MovementType.SALIDA_MANUAL: ("#FEF3C7", "#92400E"),
            MovementType.CONSUMO_PRODUCCION: ("#F3D6DB", "#773344"),
            MovementType.AJUSTE_MERMA: ("#FEE2E2", "#991B1B"),
            MovementType.DEVOLUCION: ("#E0E7FF", "#3730A3"),
        }
        bg, text = colores.get(obj.movement_type, ("#F3F4F6", "#374151"))
        return format_html(
            f'<span style="background-color: {bg}; color: {text}; padding: 3px 8px; border-radius: 9999px; font-weight: bold; font-size: 11px;">{obj.get_movement_type_display()}</span>'
        )

    # Restringir adición, edición y eliminación para garantizar inmutabilidad
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
