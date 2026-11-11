"""
Vistas API REST para Despacho y Logística - Dulce Arte.
Gestiona rutas de entrega, asignación de repartidores y confirmación de entregas con firma digital.
"""

from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.exceptions import BusinessLogicException, DeliveryAlreadyConfirmedException
from apps.dispatch.models import DeliveryRoute, DispatchOrder, DispatchStatus
from apps.dispatch.services import DispatchService
from apps.users.models import User, UserRole
from apps.users.permissions import IsAdminRole, IsDeliveryRole, IsSalesOrAdminOrReadOnly

from .serializers import (
    AssignDispatchesInputSerializer,
    ConfirmDeliveryInputSerializer,
    CreateRouteInputSerializer,
    DeliveryProofSerializer,
    DeliveryRouteSerializer,
    DispatchOrderSerializer,
)


class DeliveryRouteViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet de rutas de despacho.
    - Lectura: ADMIN y VENTAS.
    - Creación, inicio y asignación: solo ADMIN o VENTAS (IsSalesOrAdminOrReadOnly).
    """

    serializer_class = DeliveryRouteSerializer
    permission_classes = [IsSalesOrAdminOrReadOnly]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["scheduled_date", "status", "created_at"]
    ordering = ["-scheduled_date"]

    def get_queryset(self):
        return (
            DeliveryRoute.objects.select_related("assigned_driver")
            .prefetch_related("dispatches__order__client", "dispatches__assigned_driver", "dispatches__proof")
            .order_by("-scheduled_date")
        )

    @action(detail=False, methods=["post"], permission_classes=[IsSalesOrAdminOrReadOnly])
    def create_route(self, request):
        """
        Crea una nueva hoja de ruta con código RT-YYYY-XXXXX.
        """
        serializer = CreateRouteInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        driver = None
        if data.get("driver_id"):
            try:
                driver = User.objects.get(id=data["driver_id"], role=UserRole.REPARTIDOR)
            except User.DoesNotExist:
                return Response(
                    {"detail": "No se encontró un usuario con rol REPARTIDOR para el ID proporcionado."},
                    status=status.HTTP_404_NOT_FOUND,
                )

        route = DispatchService.create_route(
            scheduled_date=data["scheduled_date"],
            driver_user=driver,
            notes=data.get("notes", ""),
        )
        return Response(
            DeliveryRouteSerializer(route, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"], permission_classes=[IsSalesOrAdminOrReadOnly])
    def assign_stops(self, request, pk=None):
        """
        Asigna despachos a una ruta con orden de parada secuencial.
        Body: { "stops": [{"dispatch_id": "<uuid>", "stop_order": 1}, ...] }
        """
        route = self.get_object()
        serializer = AssignDispatchesInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        stops_data = [
            {"dispatch_id": str(stop["dispatch_id"]), "stop_order": stop["stop_order"]}
            for stop in serializer.validated_data["stops"]
        ]

        try:
            updated_route = DispatchService.assign_dispatches_to_route(route=route, dispatch_stops=stops_data)
        except (DispatchOrder.DoesNotExist, BusinessLogicException) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                "detail": f"Se asignaron {len(stops_data)} paradas a la ruta '{updated_route.code}'.",
                "route": DeliveryRouteSerializer(updated_route, context={"request": request}).data,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], permission_classes=[IsSalesOrAdminOrReadOnly])
    def start_route(self, request, pk=None):
        """
        Inicia el recorrido de la ruta; los despachos pasan a EN_RUTA
        y los pedidos asociados pasan a EN_DESPACHO.
        """
        route = self.get_object()
        try:
            updated_route = DispatchService.start_route(route=route, user=request.user)
        except BusinessLogicException as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                "detail": f"Ruta '{updated_route.code}' iniciada. Repartidores en camino.",
                "route": DeliveryRouteSerializer(updated_route, context={"request": request}).data,
            },
            status=status.HTTP_200_OK,
        )


class DispatchOrderViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet de despachos individuales.
    - Lectura: todos los autenticados.
    - my_deliveries: filtra por repartidor autenticado.
    - confirm: solo REPARTIDOR o ADMIN.
    """

    serializer_class = DispatchOrderSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["stop_order", "status", "dispatched_at"]

    def get_queryset(self):
        return (
            DispatchOrder.objects.select_related(
                "order__client",
                "route",
                "assigned_driver",
                "proof",
            )
            .order_by("route", "stop_order")
        )

    @action(detail=False, methods=["get"], permission_classes=[IsAuthenticated])
    def my_deliveries(self, request):
        """
        Retorna los despachos asignados al repartidor autenticado actualmente en ruta.
        Útil para la vista móvil/táctil del repartidor.
        """
        qs = self.get_queryset().filter(
            assigned_driver=request.user,
            status__in=[DispatchStatus.PENDIENTE, DispatchStatus.EN_RUTA],
        )
        serializer = DispatchOrderSerializer(qs, many=True, context={"request": request})
        return Response(
            {"count": qs.count(), "results": serializer.data},
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], permission_classes=[IsDeliveryRole])
    def confirm(self, request, pk=None):
        """
        Certifica la entrega de un pedido mediante firma digital o foto comprobante.
        Solo el REPARTIDOR asignado o un ADMIN pueden confirmar.
        Garantiza idempotencia: impide doble confirmación.
        """
        dispatch = self.get_object()

        # Verificar que el repartidor autenticado es el asignado (o es ADMIN)
        if not request.user.is_admin and dispatch.assigned_driver != request.user:
            return Response(
                {"detail": "No tienes permiso para confirmar este despacho. Solo el repartidor asignado puede hacerlo."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = ConfirmDeliveryInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            proof = DispatchService.confirm_delivery(
                dispatch_order=dispatch,
                recipient_name=data["recipient_name"],
                recipient_id=data["recipient_id"],
                signature_data=data["signature_data"],
                proof_photo=data.get("proof_photo"),
                user=request.user,
            )
        except DeliveryAlreadyConfirmedException as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        except BusinessLogicException as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                "detail": f"Entrega del pedido '{dispatch.order.order_number}' confirmada y certificada exitosamente.",
                "proof": DeliveryProofSerializer(proof, context={"request": request}).data,
            },
            status=status.HTTP_201_CREATED,
        )
