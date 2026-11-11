"""
Serializers para la API REST de Despacho y Logística - Dulce Arte.
"""

from rest_framework import serializers

from apps.dispatch.models import DeliveryProof, DeliveryRoute, DispatchOrder, RouteStatus


class DeliveryProofSerializer(serializers.ModelSerializer):
    """Serializer de lectura para comprobantes de entrega."""

    class Meta:
        model = DeliveryProof
        fields = [
            "id",
            "recipient_name",
            "recipient_id",
            "signature_data",
            "proof_photo",
            "registered_at",
        ]


class DispatchOrderSerializer(serializers.ModelSerializer):
    """Serializer de lectura para despachos individuales."""

    status_display = serializers.CharField(source="get_status_display", read_only=True)
    order_number = serializers.CharField(source="order.order_number", read_only=True)
    order_client = serializers.CharField(source="order.client.name", read_only=True)
    delivery_address = serializers.CharField(source="order.delivery_address", read_only=True)
    assigned_driver_name = serializers.SerializerMethodField()
    proof = DeliveryProofSerializer(read_only=True)

    class Meta:
        model = DispatchOrder
        fields = [
            "id",
            "order_number",
            "order_client",
            "delivery_address",
            "stop_order",
            "status",
            "status_display",
            "assigned_driver_name",
            "dispatched_at",
            "delivered_at",
            "proof",
            "created_at",
        ]

    def get_assigned_driver_name(self, obj) -> str | None:
        if obj.assigned_driver:
            return obj.assigned_driver.get_full_name() or obj.assigned_driver.username
        return None


class DeliveryRouteSerializer(serializers.ModelSerializer):
    """Serializer de lectura para rutas de despacho."""

    status_display = serializers.CharField(source="get_status_display", read_only=True)
    assigned_driver_name = serializers.SerializerMethodField()
    dispatches = DispatchOrderSerializer(many=True, read_only=True)

    class Meta:
        model = DeliveryRoute
        fields = [
            "id",
            "code",
            "scheduled_date",
            "status",
            "status_display",
            "notes",
            "assigned_driver_name",
            "dispatches",
            "created_at",
        ]

    def get_assigned_driver_name(self, obj) -> str | None:
        if obj.assigned_driver:
            return obj.assigned_driver.get_full_name() or obj.assigned_driver.username
        return None


class CreateRouteInputSerializer(serializers.Serializer):
    """Serializer de entrada para crear una ruta de despacho."""

    scheduled_date = serializers.DateField(
        help_text="Fecha programada para el recorrido.",
    )
    driver_id = serializers.UUIDField(
        required=False,
        allow_null=True,
        help_text="ID del usuario con rol REPARTIDOR a asignar (opcional al crear).",
    )
    notes = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        max_length=500,
    )


class DispatchStopInputSerializer(serializers.Serializer):
    """Un ítem de parada al asignar despachos a una ruta."""

    dispatch_id = serializers.UUIDField()
    stop_order = serializers.IntegerField(min_value=1)


class AssignDispatchesInputSerializer(serializers.Serializer):
    """Serializer de entrada para asignar despachos a una ruta."""

    stops = DispatchStopInputSerializer(many=True, min_length=1)

    def validate_stops(self, stops):
        dispatch_ids = [item["dispatch_id"] for item in stops]
        stop_orders = [item["stop_order"] for item in stops]
        if len(dispatch_ids) != len(set(dispatch_ids)):
            raise serializers.ValidationError("Un despacho solo puede aparecer una vez en la ruta.")
        if len(stop_orders) != len(set(stop_orders)):
            raise serializers.ValidationError("No se puede repetir el número de parada en una ruta.")
        return stops


class ConfirmDeliveryInputSerializer(serializers.Serializer):
    """Serializer de entrada para confirmar una entrega con firma digital."""

    recipient_name = serializers.CharField(
        max_length=150,
        help_text="Nombre completo de la persona que recibe el pedido.",
    )
    recipient_id = serializers.CharField(
        max_length=25,
        help_text="RUT o DNI del receptor.",
    )
    signature_data = serializers.CharField(
        help_text="Firma digital codificada en DataURI SVG o Base64.",
    )
    proof_photo = serializers.ImageField(
        required=False,
        allow_null=True,
        help_text="Fotografía opcional del comprobante de entrega.",
    )
