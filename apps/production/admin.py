"""
Administración avanzada para Producción, Kanban y Control de Calidad en Dulce Arte.
Permite visualizar la asignación de pasteleros y el estatus de stock descontado.
"""

from django.contrib import admin
from django.utils.html import format_html
from .models import KanbanStage, ProductionOrder, QualityCheck, QualityResult


class QualityCheckInline(admin.StackedInline):
    """Control de calidad inline dentro de la orden de producción."""

    model = QualityCheck
    extra = 0
    can_delete = False


@admin.register(ProductionOrder)
class ProductionOrderAdmin(admin.ModelAdmin):
    list_display = (
        "production_code",
        "order",
        "kanban_stage_badge",
        "assigned_cook",
        "stock_consumed_badge",
        "started_at",
        "finished_at",
    )
    list_filter = ("kanban_stage", "stock_consumed")
    search_fields = (
        "production_code",
        "order__order_number",
        "assigned_cook__username",
        "assigned_cook__first_name",
        "assigned_cook__last_name",
    )
    readonly_fields = ("production_code", "created_at", "updated_at")
    ordering = ["kanban_stage", "-created_at"]
    list_select_related = ("order", "assigned_cook")
    inlines = [QualityCheckInline]

    fieldsets = (
        (
            "Identificación de Producción",
            {
                "fields": ("production_code", "order", "kanban_stage"),
            },
        ),
        (
            "Asignación y Consumo",
            {
                "fields": ("assigned_cook", "stock_consumed"),
            },
        ),
        (
            "Tiempos Operativos",
            {
                "fields": ("started_at", "finished_at", "notes"),
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

    @admin.display(description="Etapa Kanban")
    def kanban_stage_badge(self, obj):
        colores = {
            KanbanStage.RECIBIDO: ("#E0E7FF", "#3730A3"),
            KanbanStage.EN_PREPARACION: ("#FEF3C7", "#92400E"),
            KanbanStage.HORNEADO_DECORADO: ("#F3D6DB", "#773344"),
            KanbanStage.CONTROL_CALIDAD: ("#E0E7FF", "#1E40AF"),
            KanbanStage.LISTO: ("#DCEBDD", "#2d5a33"),
        }
        bg, text = colores.get(obj.kanban_stage, ("#F3F4F6", "#374151"))
        return format_html(
            f'<span style="background-color: {bg}; color: {text}; padding: 3px 8px; border-radius: 9999px; font-weight: bold; font-size: 11px;">{obj.get_kanban_stage_display()}</span>'
        )

    @admin.display(description="Stock Descontado")
    def stock_consumed_badge(self, obj):
        if obj.stock_consumed:
            return format_html(
                '<span style="background-color: #DCEBDD; color: #2d5a33; padding: 2px 7px; border-radius: 9999px; font-size: 11px; font-weight: bold;">✓ Descontado</span>'
            )
        return format_html(
            '<span style="background-color: #FEE2E2; color: #991B1B; padding: 2px 7px; border-radius: 9999px; font-size: 11px; font-weight: bold;">Pendiente</span>'
        )


@admin.register(QualityCheck)
class QualityCheckAdmin(admin.ModelAdmin):
    list_display = ("production_order", "inspected_by", "result_badge", "created_at")
    list_filter = ("result", "created_at")
    search_fields = ("production_order__production_code", "inspected_by__username")
    readonly_fields = ("created_at", "updated_at")
    list_select_related = ("production_order", "inspected_by")

    @admin.display(description="Resultado")
    def result_badge(self, obj):
        colores = {
            QualityResult.APROBADO: ("#DCEBDD", "#2d5a33"),
            QualityResult.RECHAZADO: ("#FEE2E2", "#991B1B"),
            QualityResult.REQUIERE_AJUSTE: ("#FEF3C7", "#92400E"),
        }
        bg, text = colores.get(obj.result, ("#F3F4F6", "#374151"))
        return format_html(
            f'<span style="background-color: {bg}; color: {text}; padding: 3px 8px; border-radius: 9999px; font-weight: bold; font-size: 11px;">{obj.get_result_display()}</span>'
        )
