"""
Vistas API REST para Inventario, Insumos y Movimientos en Dulce Arte.
"""

from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from apps.inventory.models import StockMovement, Supply, UnitOfMeasure
from apps.inventory.services import InventoryService
from apps.users.permissions import IsAdminOrReadOnly, IsAdminRole, IsKitchenRole
from .serializers import (
    StockEntryInputSerializer,
    StockMovementSerializer,
    StockWasteInputSerializer,
    SupplyCreateUpdateSerializer,
    SupplySerializer,
    UnitOfMeasureSerializer,
)


class UnitOfMeasureViewSet(viewsets.ModelViewSet):
    queryset = UnitOfMeasure.objects.all().order_by("magnitude", "code")
    serializer_class = UnitOfMeasureSerializer
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [filters.SearchFilter]
    search_fields = ["code", "name"]


class SupplyViewSet(viewsets.ModelViewSet):
    """
    Gestión de insumos con filtrado, búsqueda y protección de eliminación lógica.
    """

    queryset = Supply.objects.all().select_related("unit_of_measure").order_by("name")
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["sku", "name"]
    ordering_fields = ["name", "current_stock", "created_at"]

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return SupplyCreateUpdateSerializer
        return SupplySerializer

    def perform_destroy(self, instance):
        instance.soft_delete()

    @action(detail=True, methods=["get"], permission_classes=[IsAuthenticated])
    def movements(self, request, pk=None):
        """Lista el historial de movimientos de un insumo específico."""
        supply = self.get_object()
        movements = supply.movements.select_related("user").order_by("-created_at")
        page = self.paginate_queryset(movements)
        if page is not None:
            serializer = StockMovementSerializer(page, many=True, context={"request": request})
            return self.get_paginated_response(serializer.data)
        serializer = StockMovementSerializer(movements, many=True, context={"request": request})
        return Response(serializer.data)


class StockMovementViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Historial de movimientos de stock (solo lectura) y acciones para registrar entradas y mermas.
    """

    queryset = StockMovement.objects.all().select_related("supply", "supply__unit_of_measure", "user").order_by("-created_at")
    serializer_class = StockMovementSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["supply__name", "supply__sku", "reference", "user__username"]
    ordering_fields = ["created_at", "quantity"]

    @action(detail=False, methods=["post"], permission_classes=[IsAdminRole])
    def entry(self, request):
        """Registra una entrada de inventario por compra."""
        serializer = StockEntryInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        supply = get_object_or_404(Supply, id=serializer.validated_data["supply_id"])
        movement = InventoryService.register_entry(
            supply=supply,
            quantity=serializer.validated_data["quantity"],
            user=request.user,
            reference=serializer.validated_data.get("reference", ""),
            notes=serializer.validated_data.get("notes", ""),
        )

        return Response(
            {
                "detail": "Entrada de inventario registrada exitosamente.",
                "movement": StockMovementSerializer(movement, context={"request": request}).data,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=["post"], permission_classes=[IsKitchenRole])
    def waste(self, request):
        """Registra una merma justificada por parte de cocina o administración."""
        serializer = StockWasteInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        supply = get_object_or_404(Supply, id=serializer.validated_data["supply_id"])
        movement = InventoryService.register_waste(
            supply=supply,
            quantity=serializer.validated_data["quantity"],
            user=request.user,
            reference=serializer.validated_data.get("reference", ""),
            notes=serializer.validated_data.get("notes", ""),
        )

        return Response(
            {
                "detail": "Merma registrada exitosamente.",
                "movement": StockMovementSerializer(movement, context={"request": request}).data,
            },
            status=status.HTTP_201_CREATED,
        )
