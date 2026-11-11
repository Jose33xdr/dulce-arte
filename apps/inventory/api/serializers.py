"""
Serializadores para el módulo de Inventario en la API REST de Dulce Arte.
Protege la exposición de costos unitarios según el rol del usuario solicitante.
"""

from decimal import Decimal
from rest_framework import serializers
from apps.inventory.models import StockMovement, Supply, UnitOfMeasure


class UnitOfMeasureSerializer(serializers.ModelSerializer):
    magnitude_display = serializers.CharField(source="get_magnitude_display", read_only=True)

    class Meta:
        model = UnitOfMeasure
        fields = [
            "code",
            "name",
            "magnitude",
            "magnitude_display",
            "conversion_factor",
            "is_active",
        ]


class SupplySerializer(serializers.ModelSerializer):
    """
    Serializador de lectura de insumos.
    Oculta el costo unitario interno a usuarios que no posean rol de Administrador.
    """

    unit_code = serializers.CharField(source="unit_of_measure.code", read_only=True)
    unit_name = serializers.CharField(source="unit_of_measure.name", read_only=True)
    is_low_stock = serializers.BooleanField(read_only=True)

    class Meta:
        model = Supply
        fields = [
            "id",
            "sku",
            "name",
            "unit_of_measure",
            "unit_code",
            "unit_name",
            "current_stock",
            "minimum_stock",
            "cost_per_unit",
            "is_low_stock",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "is_low_stock", "created_at", "updated_at"]

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        request = self.context.get("request")
        # Si el usuario no es administrador, no exponer el costo unitario
        if request and hasattr(request, "user") and not request.user.is_admin:
            ret.pop("cost_per_unit", None)
        return ret


class SupplyCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializador para creación y edición de insumos (uso exclusivo de administradores)."""

    class Meta:
        model = Supply
        fields = [
            "id",
            "sku",
            "name",
            "unit_of_measure",
            "current_stock",
            "minimum_stock",
            "cost_per_unit",
            "is_active",
        ]


class StockMovementSerializer(serializers.ModelSerializer):
    """Serializador de solo lectura para el historial de movimientos de inventario."""

    supply_name = serializers.CharField(source="supply.name", read_only=True)
    supply_sku = serializers.CharField(source="supply.sku", read_only=True)
    unit_code = serializers.CharField(source="supply.unit_of_measure.code", read_only=True)
    movement_type_display = serializers.CharField(source="get_movement_type_display", read_only=True)
    user_name = serializers.CharField(source="user.get_full_name", read_only=True)

    class Meta:
        model = StockMovement
        fields = [
            "id",
            "supply",
            "supply_sku",
            "supply_name",
            "unit_code",
            "movement_type",
            "movement_type_display",
            "quantity",
            "stock_before",
            "stock_after",
            "user",
            "user_name",
            "reference",
            "notes",
            "created_at",
        ]
        read_only_fields = fields


class StockEntryInputSerializer(serializers.Serializer):
    """Validación de entrada para compra o recepción de insumo."""

    supply_id = serializers.UUIDField(required=True)
    quantity = serializers.DecimalField(max_digits=12, decimal_places=3, required=True, min_value=Decimal("0.001"))
    reference = serializers.CharField(max_length=100, required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)


class StockWasteInputSerializer(serializers.Serializer):
    """Validación de entrada para registro de merma o desecho."""

    supply_id = serializers.UUIDField(required=True)
    quantity = serializers.DecimalField(max_digits=12, decimal_places=3, required=True, min_value=Decimal("0.001"))
    reference = serializers.CharField(max_length=100, required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)
