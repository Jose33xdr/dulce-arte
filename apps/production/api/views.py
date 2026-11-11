"""
Vistas API REST para Producción Kanban - Dulce Arte.
Gestiona el avance de órdenes de cocina mediante el tablero Kanban y controles de calidad.
"""

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.exceptions import BusinessLogicException, InvalidStateTransitionException
from apps.production.models import KanbanStage, ProductionOrder
from apps.production.services import ProductionService
from apps.users.models import User, UserRole
from apps.users.permissions import IsAdminRole, IsKitchenOrAdminOrReadOnly

from .serializers import (
    AssignCookInputSerializer,
    ProductionOrderSerializer,
    QualityCheckInputSerializer,
    QualityCheckSerializer,
    TransitionInputSerializer,
)


class ProductionOrderViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet de órdenes de producción.
    - Lectura disponible para ADMIN, VENTAS y COCINA.
    - Transiciones, control de calidad y asignación solo para COCINA o ADMIN.
    """

    serializer_class = ProductionOrderSerializer
    permission_classes = [IsKitchenOrAdminOrReadOnly]

    def get_queryset(self):
        return (
            ProductionOrder.objects.select_related(
                "order__client",
                "assigned_cook",
            )
            .prefetch_related("quality_check")
            .order_by("kanban_stage", "-created_at")
        )

    @action(detail=False, methods=["get"], permission_classes=[IsAuthenticated])
    def kanban(self, request):
        """
        Retorna todas las órdenes agrupadas por etapa Kanban.
        Útil para renderizar columnas del tablero.
        """
        qs = self.get_queryset()
        stage_filter = request.query_params.get("stage")
        if stage_filter:
            qs = qs.filter(kanban_stage=stage_filter)

        grouped: dict[str, list] = {stage: [] for stage in KanbanStage.values}
        for prod_order in qs:
            serialized = ProductionOrderSerializer(prod_order, context={"request": request}).data
            grouped[prod_order.kanban_stage].append(serialized)

        return Response(
            {
                "stages": KanbanStage.choices,
                "board": grouped,
                "total": qs.count(),
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], permission_classes=[IsKitchenOrAdminOrReadOnly])
    def transition(self, request, pk=None):
        """
        Avanza la orden de producción a la siguiente etapa Kanban.
        Al ingresar a EN_PREPARACION descuenta el inventario atómicamente.
        Al ingresar a LISTO exige control de calidad aprobado.
        """
        prod_order = self.get_object()
        serializer = TransitionInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            updated = ProductionService.transition_stage(
                production_order=prod_order,
                target_stage=serializer.validated_data["target_stage"],
                user=request.user,
                notes=serializer.validated_data.get("notes", ""),
            )
        except (InvalidStateTransitionException, BusinessLogicException) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                "detail": f"Orden avanzada correctamente a etapa '{updated.get_kanban_stage_display()}'.",
                "production_order": ProductionOrderSerializer(updated, context={"request": request}).data,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], permission_classes=[IsKitchenOrAdminOrReadOnly])
    def quality_check(self, request, pk=None):
        """
        Registra o actualiza el control de calidad de una orden.
        Solo aplicable cuando la orden está en etapa CONTROL_CALIDAD.
        """
        prod_order = self.get_object()

        if prod_order.kanban_stage != KanbanStage.CONTROL_CALIDAD:
            return Response(
                {
                    "detail": (
                        f"El control de calidad solo se puede registrar en la etapa "
                        f"'{KanbanStage.CONTROL_CALIDAD.label}'. "
                        f"Etapa actual: '{prod_order.get_kanban_stage_display()}'."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = QualityCheckInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        qc = ProductionService.record_quality_check(
            production_order=prod_order,
            inspector_user=request.user,
            result=serializer.validated_data["result"],
            observations=serializer.validated_data.get("observations", ""),
        )

        return Response(
            {
                "detail": f"Control de calidad registrado con resultado '{qc.get_result_display()}'.",
                "quality_check": QualityCheckSerializer(qc, context={"request": request}).data,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], permission_classes=[IsAdminRole])
    def assign_cook(self, request, pk=None):
        """
        Asigna un pastelero responsable a la orden de producción. Solo ADMIN.
        """
        prod_order = self.get_object()
        serializer = AssignCookInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            cook = User.objects.get(id=serializer.validated_data["cook_id"], role=UserRole.COCINA)
        except User.DoesNotExist:
            return Response(
                {"detail": "No se encontró un usuario con rol COCINA para el ID proporcionado."},
                status=status.HTTP_404_NOT_FOUND,
            )

        updated = ProductionService.assign_cook(prod_order, cook)
        return Response(
            {
                "detail": f"Cocinero '{cook.get_full_name()}' asignado correctamente.",
                "production_order": ProductionOrderSerializer(updated, context={"request": request}).data,
            },
            status=status.HTTP_200_OK,
        )
