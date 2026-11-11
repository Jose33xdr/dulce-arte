"""
Serializadores para Pedidos, Cotizaciones y Personalizaciones en la API REST de Dulce Arte.
"""

from decimal import Decimal
from rest_framework import serializers
from apps.clients.api.serializers import ClientSerializer
from apps.orders.models import DeliveryType, Order, OrderItem, OrderStatus, OrderStatusHistory
from apps.recipes.models import Product


class OrderItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_code = serializers.CharField(source="product.code", read_only=True)

    class Meta:
        model = OrderItem
        fields = [
            "id",
            "product",
            "product_code",
            "product_name",
            "quantity",
            "unit_price",
            "subtotal",
            "cake_size",
            "flavor_sponge",
            "flavor_filling",
            "flavor_cover",
            "custom_dedication",
            "customizations",
        ]
        read_only_fields = ["id", "subtotal"]


class OrderStatusHistorySerializer(serializers.ModelSerializer):
    changed_by_name = serializers.CharField(source="changed_by.get_full_name", read_only=True)

    class Meta:
        model = OrderStatusHistory
        fields = [
            "id",
            "previous_status",
            "new_status",
            "changed_by",
            "changed_by_name",
            "reason",
            "created_at",
        ]
        read_only_fields = fields


class OrderListSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(source="client.name", read_only=True)
    client_identification = serializers.CharField(source="client.identification", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    delivery_type_display = serializers.CharField(source="get_delivery_type_display", read_only=True)
    items_count = serializers.IntegerField(source="items.count", read_only=True)

    class Meta:
        model = Order
        fields = [
            "id",
            "order_number",
            "client",
            "client_name",
            "client_identification",
            "status",
            "status_display",
            "delivery_date",
            "delivery_time",
            "delivery_type",
            "delivery_type_display",
            "total_amount",
            "deposit_amount",
            "balance_due",
            "items_count",
            "created_at",
        ]
        read_only_fields = fields


class OrderDetailSerializer(serializers.ModelSerializer):
    client = ClientSerializer(read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    delivery_type_display = serializers.CharField(source="get_delivery_type_display", read_only=True)
    items = OrderItemSerializer(many=True, read_only=True)
    status_history = OrderStatusHistorySerializer(many=True, read_only=True)
    production_code = serializers.CharField(source="production_order.production_code", read_only=True, default=None)
    kanban_stage = serializers.CharField(source="production_order.kanban_stage", read_only=True, default=None)
    dispatch_status = serializers.CharField(source="dispatch_order.status", read_only=True, default=None)

    class Meta:
        model = Order
        fields = [
            "id",
            "order_number",
            "client",
            "status",
            "status_display",
            "delivery_date",
            "delivery_time",
            "delivery_type",
            "delivery_type_display",
            "delivery_address",
            "total_amount",
            "deposit_amount",
            "balance_due",
            "custom_design_notes",
            "reference_image",
            "items",
            "production_code",
            "kanban_stage",
            "dispatch_status",
            "status_history",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class OrderItemInputSerializer(serializers.Serializer):
    product_id = serializers.UUIDField(required=True)
    quantity = serializers.IntegerField(required=True, min_value=1)
    unit_price = serializers.DecimalField(max_digits=12, decimal_places=2, required=False)
    cake_size = serializers.CharField(max_length=50, required=False, allow_blank=True)
    flavor_sponge = serializers.CharField(max_length=60, required=False, allow_blank=True)
    flavor_filling = serializers.CharField(max_length=100, required=False, allow_blank=True)
    flavor_cover = serializers.CharField(max_length=60, required=False, allow_blank=True)
    custom_dedication = serializers.CharField(max_length=150, required=False, allow_blank=True)
    customizations = serializers.CharField(required=False, allow_blank=True)


class OrderCreateInputSerializer(serializers.Serializer):
    client_id = serializers.UUIDField(required=True)
    delivery_date = serializers.DateField(required=True)
    delivery_time = serializers.TimeField(required=True)
    delivery_type = serializers.ChoiceField(choices=DeliveryType.choices, default=DeliveryType.RETIRO_TIENDA)
    delivery_address = serializers.CharField(max_length=255, required=False, allow_blank=True)
    deposit_amount = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, default=Decimal("0.00"))
    custom_design_notes = serializers.CharField(required=False, allow_blank=True)
    status = serializers.ChoiceField(choices=[OrderStatus.COTIZACION, OrderStatus.CONFIRMADO], default=OrderStatus.COTIZACION)
    items = OrderItemInputSerializer(many=True, required=True)


class OrderUpdateInputSerializer(serializers.ModelSerializer):
    """Campos comerciales editables mientras el pedido sigue siendo cotización."""

    class Meta:
        model = Order
        fields = [
            "delivery_date",
            "delivery_time",
            "delivery_type",
            "delivery_address",
            "deposit_amount",
            "custom_design_notes",
            "reference_image",
        ]

    def validate(self, attrs):
        instance = self.instance
        delivery_type = attrs.get("delivery_type", instance.delivery_type)
        delivery_address = attrs.get("delivery_address", instance.delivery_address)
        if delivery_type == DeliveryType.DESPACHO_DOMICILIO and not delivery_address and not instance.client.address:
            raise serializers.ValidationError({"delivery_address": "Para despacho a domicilio debe especificar una dirección de entrega."})

        deposit = attrs.get("deposit_amount", instance.deposit_amount)
        if deposit > instance.total_amount:
            raise serializers.ValidationError({"deposit_amount": "El monto de abono no puede superar el monto total del pedido."})
        return attrs

    def update(self, instance, validated_data):
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.balance_due = instance.total_amount - instance.deposit_amount
        instance.full_clean()
        instance.save()
        return instance


class OrderConfirmInputSerializer(serializers.Serializer):
    deposit_amount = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, min_value=Decimal("0.00"))
    reason = serializers.CharField(max_length=255, required=False, default="Confirmación formal del pedido con abono.")


class OrderCancelInputSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=255, required=True)
