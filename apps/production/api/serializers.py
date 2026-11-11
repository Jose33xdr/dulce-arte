"""
Serializers para la API REST de Producción Kanban - Dulce Arte.
"""

from rest_framework import serializers

from apps.production.models import KanbanStage, ProductionOrder, QualityCheck, QualityResult
from apps.orders.models import Order


class QualityCheckSerializer(serializers.ModelSerializer):
    """Serializer de lectura para control de calidad."""

    inspected_by_name = serializers.SerializerMethodField()
    result_display = serializers.CharField(source="get_result_display", read_only=True)

    class Meta:
        model = QualityCheck
        fields = [
            "id",
            "result",
            "result_display",
            "observations",
            "inspected_by_name",
            "created_at",
        ]

    def get_inspected_by_name(self, obj) -> str:
        return obj.inspected_by.get_full_name() or obj.inspected_by.username


class ProductionOrderSerializer(serializers.ModelSerializer):
    """Serializer de lectura para órdenes de producción."""

    kanban_stage_display = serializers.CharField(source="get_kanban_stage_display", read_only=True)
    order_number = serializers.CharField(source="order.order_number", read_only=True)
    order_client = serializers.CharField(source="order.client.name", read_only=True)
    order_delivery_date = serializers.DateField(source="order.delivery_date", read_only=True)
    order_delivery_time = serializers.TimeField(source="order.delivery_time", read_only=True)
    assigned_cook_name = serializers.SerializerMethodField()
    quality_check = QualityCheckSerializer(read_only=True)

    class Meta:
        model = ProductionOrder
        fields = [
            "id",
            "production_code",
            "kanban_stage",
            "kanban_stage_display",
            "stock_consumed",
            "started_at",
            "finished_at",
            "notes",
            "assigned_cook_name",
            "order_number",
            "order_client",
            "order_delivery_date",
            "order_delivery_time",
            "quality_check",
            "created_at",
            "updated_at",
        ]

    def get_assigned_cook_name(self, obj) -> str | None:
        if obj.assigned_cook:
            return obj.assigned_cook.get_full_name() or obj.assigned_cook.username
        return None


class TransitionInputSerializer(serializers.Serializer):
    """Serializer de entrada para transiciones de etapa Kanban."""

    target_stage = serializers.ChoiceField(
        choices=KanbanStage.choices,
        help_text="Etapa de destino en el flujo Kanban.",
    )
    notes = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        max_length=500,
        help_text="Notas de producción opcionales para la transición.",
    )


class QualityCheckInputSerializer(serializers.Serializer):
    """Serializer de entrada para registrar un control de calidad."""

    result = serializers.ChoiceField(
        choices=QualityResult.choices,
        help_text="Resultado del control: APROBADO, RECHAZADO o REQUIERE_AJUSTE.",
    )
    observations = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        max_length=1000,
        help_text="Observaciones del inspector: peso, temperatura, presentación visual.",
    )


class AssignCookInputSerializer(serializers.Serializer):
    """Serializer de entrada para asignar un cocinero a la orden."""

    cook_id = serializers.IntegerField(
        help_text="ID del usuario con rol COCINA a asignar.",
    )
