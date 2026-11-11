"""
Vistas API REST para Pedidos, Cotizaciones y Personalizaciones en Dulce Arte.
"""

from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from apps.clients.models import Client
from apps.inventory.services import InventoryService
from apps.orders.models import Order, OrderStatus
from apps.orders.services import OrderService
from apps.recipes.models import Product
from apps.recipes.services import RecipeService
from apps.users.permissions import IsAdminRole, IsSalesOrAdminOrReadOnly
from .serializers import (
    OrderCancelInputSerializer,
    OrderConfirmInputSerializer,
    OrderCreateInputSerializer,
    OrderDetailSerializer,
    OrderListSerializer,
    OrderUpdateInputSerializer,
)


class OrderViewSet(viewsets.ModelViewSet):
    """
    CRUD de pedidos y cotizaciones con acciones específicas de negocio.
    Restringe queryset según rol: Cocina solo lectura, Repartidor sin acceso.
    """

    permission_classes = [IsSalesOrAdminOrReadOnly]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["order_number", "client__name", "client__identification"]
    ordering_fields = ["delivery_date", "created_at", "total_amount"]

    def get_queryset(self):
        user = self.request.user
        qs = Order.objects.select_related("client").prefetch_related(
            "items__product",
            "status_history__changed_by",
        ).order_by("-delivery_date")

        # Filtros opcionales por query params
        status_param = self.request.query_params.get("status")
        if status_param:
            qs = qs.filter(status=status_param)
        return qs

    def get_serializer_class(self):
        if self.action in ["retrieve", "bom_check", "confirm", "cancel"]:
            return OrderDetailSerializer
        if self.action in ["update", "partial_update"]:
            return OrderUpdateInputSerializer
        return OrderListSerializer

    def create(self, request, *args, **kwargs):
        serializer = OrderCreateInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            client = Client.objects.get(id=data["client_id"], is_active=True)
        except Client.DoesNotExist:
            return Response({"client_id": ["No existe un cliente activo con este identificador."]}, status=status.HTTP_400_BAD_REQUEST)

        # Resolver productos desde IDs
        items_resolved = []
        for item_data in data["items"]:
            try:
                product = Product.objects.get(id=item_data["product_id"], is_active=True)
            except Product.DoesNotExist:
                return Response(
                    {"items": [f"No existe un producto activo con ID {item_data['product_id']}. "]},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            items_resolved.append({
                "product": product,
                **{k: v for k, v in item_data.items() if k != "product_id"},
            })

        order = OrderService.create_order(
            client=client,
            delivery_date=data["delivery_date"],
            delivery_time=data["delivery_time"],
            items_data=items_resolved,
            delivery_type=data.get("delivery_type", "RETIRO_TIENDA"),
            delivery_address=data.get("delivery_address", ""),
            deposit_amount=data.get("deposit_amount", 0),
            custom_design_notes=data.get("custom_design_notes", ""),
            user=request.user,
            status=data.get("status", OrderStatus.COTIZACION),
        )

        return Response(OrderDetailSerializer(order, context={"request": request}).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        """Solo permite editar pedidos en estado COTIZACION."""
        order = self.get_object()
        if order.status not in [OrderStatus.COTIZACION]:
            return Response(
                {"detail": f"Solo se pueden editar pedidos en estado COTIZACION. Estado actual: '{order.get_status_display()}'."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        partial = kwargs.pop("partial", False)
        serializer = self.get_serializer(order, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        updated = serializer.save()
        return Response(OrderDetailSerializer(updated, context={"request": request}).data)

    def destroy(self, request, *args, **kwargs):
        return Response(
            {"detail": "Los pedidos no pueden eliminarse físicamente. Use la acción de cancelar."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    @action(detail=True, methods=["post"], permission_classes=[IsSalesOrAdminOrReadOnly])
    def confirm(self, request, pk=None):
        """Confirma una cotización, registra el abono y emite la orden de producción."""
        order = self.get_object()
        serializer = OrderConfirmInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        confirmed = OrderService.confirm_order(
            order=order,
            deposit_amount=serializer.validated_data.get("deposit_amount"),
            user=request.user,
            reason=serializer.validated_data.get("reason", ""),
        )
        return Response(
            {"detail": "Pedido confirmado exitosamente. Orden de producción generada.", "order": OrderDetailSerializer(confirmed, context={"request": request}).data},
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], permission_classes=[IsSalesOrAdminOrReadOnly])
    def cancel(self, request, pk=None):
        """Cancela el pedido con registro del motivo."""
        order = self.get_object()
        serializer = OrderCancelInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        cancelled = OrderService.cancel_order(
            order=order,
            user=request.user,
            reason=serializer.validated_data["reason"],
        )
        return Response(
            {"detail": "Pedido cancelado y registrado en bitácora histórica.", "status": cancelled.status},
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["get"], permission_classes=[IsAuthenticated])
    def bom_check(self, request, pk=None):
        """Comprueba la disponibilidad de insumos del BOM para todos los ítems del pedido."""
        order = self.get_object()
        availability = InventoryService.check_availability_for_order(order)

        # Remover supply_object y datos de costo para no-admins
        for item in availability.get("items", []):
            item.pop("supply_object", None)
            if not request.user.is_admin:
                item.pop("cost_per_unit", None)
                item.pop("estimated_cost", None)

        return Response(availability, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"], permission_classes=[IsAuthenticated])
    def history(self, request, pk=None):
        """Retorna el historial de cambios de estado del pedido."""
        order = self.get_object()
        from .serializers import OrderStatusHistorySerializer
        history = order.status_history.select_related("changed_by").order_by("-created_at")
        serializer = OrderStatusHistorySerializer(history, many=True, context={"request": request})
        return Response(serializer.data)
