"""
Capa de servicios de despacho y logística para Dulce Arte.
Maneja rutas, paradas ordenadas, confirmación idempotente de entregas y certificación con firma digital.
"""

from typing import Dict, List, Optional
from django.db import transaction
from django.utils import timezone
from apps.core.exceptions import BusinessLogicException, DeliveryAlreadyConfirmedException
from apps.core.utils import generate_route_code
from apps.dispatch.models import DeliveryProof, DeliveryRoute, DispatchOrder, DispatchStatus, RouteStatus
from apps.orders.models import OrderStatus, OrderStatusHistory


class DispatchService:
    """
    Servicio de rutas de entrega, logística y comprobantes de recepción.
    """

    @classmethod
    def create_route(
        cls,
        scheduled_date,
        driver_user=None,
        notes: str = "",
    ) -> DeliveryRoute:
        """
        Crea una nueva hoja de ruta con código correlativo único RT-YYYY-XXXXX.
        """
        current_year = timezone.now().year
        route_count = DeliveryRoute.objects.filter(created_at__year=current_year).count() + 1
        route_code = generate_route_code(route_count)
        while DeliveryRoute.objects.filter(code=route_code).exists():
            route_count += 1
            route_code = generate_route_code(route_count)

        route = DeliveryRoute.objects.create(
            code=route_code,
            assigned_driver=driver_user,
            scheduled_date=scheduled_date,
            status=RouteStatus.PROGRAMADA,
            notes=notes,
        )
        return route

    @classmethod
    def assign_dispatches_to_route(
        cls,
        route: DeliveryRoute,
        dispatch_stops: List[Dict],
    ) -> DeliveryRoute:
        """
        Asocia despachos a una ruta asignando su orden de parada secuencial.
        dispatch_stops es una lista de dicts: [{'dispatch_id': uuid, 'stop_order': int}]
        """
        with transaction.atomic():
            route_locked = DeliveryRoute.objects.select_for_update().get(id=route.id)
            if route_locked.status != RouteStatus.PROGRAMADA:
                raise BusinessLogicException(
                    f"La ruta '{route_locked.code}' no admite cambios porque ya está {route_locked.get_status_display()}."
                )

            requested_orders = {item["stop_order"] for item in dispatch_stops}
            requested_dispatches = {str(item["dispatch_id"]) for item in dispatch_stops}
            occupied_orders = set(
                route_locked.dispatches.exclude(id__in=requested_dispatches)
                .values_list("stop_order", flat=True)
            )
            conflicts = requested_orders & occupied_orders
            if conflicts:
                conflict_list = ", ".join(str(order) for order in sorted(conflicts))
                raise BusinessLogicException(
                    f"Las paradas {conflict_list} ya están asignadas a otros despachos de la ruta."
                )

            for item in dispatch_stops:
                dispatch_id = item["dispatch_id"]
                stop_order = int(item["stop_order"])

                dispatch = DispatchOrder.objects.select_for_update().get(id=dispatch_id)
                dispatch.route = route_locked
                dispatch.stop_order = stop_order
                if route.assigned_driver:
                    dispatch.assigned_driver = route.assigned_driver
                dispatch.save(update_fields=["route", "stop_order", "assigned_driver", "updated_at"])

            return route_locked

    @classmethod
    def start_route(cls, route: DeliveryRoute, user=None) -> DeliveryRoute:
        """
        Inicia el recorrido de la ruta y pasa los pedidos a EN_DESPACHO.
        """
        with transaction.atomic():
            route_locked = DeliveryRoute.objects.select_for_update().get(id=route.id)
            if route_locked.status != RouteStatus.PROGRAMADA:
                raise BusinessLogicException(f"La ruta '{route_locked.code}' ya no se encuentra en estado Programada.")

            route_locked.status = RouteStatus.EN_CURSO
            route_locked.save(update_fields=["status", "updated_at"])

            now = timezone.now()
            for dispatch in route_locked.dispatches.select_related("order").select_for_update():
                if dispatch.status == DispatchStatus.PENDIENTE:
                    dispatch.status = DispatchStatus.EN_RUTA
                    dispatch.dispatched_at = now
                    dispatch.save(update_fields=["status", "dispatched_at", "updated_at"])

                    order = dispatch.order
                    if order.status != OrderStatus.EN_DESPACHO:
                        prev_status = order.status
                        order.status = OrderStatus.EN_DESPACHO
                        order.save(update_fields=["status", "updated_at"])
                        if user:
                            OrderStatusHistory.objects.create(
                                order=order,
                                previous_status=prev_status,
                                new_status=order.status,
                                changed_by=user,
                                reason=f"Pedido despachado en ruta {route_locked.code}.",
                            )

            return route_locked

    @classmethod
    def confirm_delivery(
        cls,
        dispatch_order: DispatchOrder,
        recipient_name: str,
        recipient_id: str,
        signature_data: str,
        proof_photo=None,
        user=None,
    ) -> DeliveryProof:
        """
        Certifica la entrega de un pedido mediante firma digital o comprobante fotográfico.
        Garantiza idempotencia: impide confirmar dos veces una entrega.
        """
        if not signature_data or not signature_data.strip():
            raise BusinessLogicException("Se requiere la firma digital del receptor para certificar la entrega.")

        if not recipient_name or not recipient_name.strip():
            raise BusinessLogicException("Debe ingresar el nombre de la persona que recibe el pedido.")

        with transaction.atomic():
            dispatch_locked = (
                # route es opcional; se bloquea exclusivamente el despacho para
                # conservar la transacción atómica sin bloquear un OUTER JOIN.
                DispatchOrder.objects.select_for_update(of=("self",))
                .select_related("order", "route")
                .get(id=dispatch_order.id)
            )

            # Regla de Negocio: Idempotencia y protección anti-doble confirmación
            if dispatch_locked.status == DispatchStatus.ENTREGADO or hasattr(dispatch_locked, "proof"):
                raise DeliveryAlreadyConfirmedException(
                    f"El despacho del pedido '{dispatch_locked.order.order_number}' "
                    f"ya fue confirmado y certificado previamente."
                )

            now = timezone.now()
            proof = DeliveryProof.objects.create(
                dispatch_order=dispatch_locked,
                recipient_name=recipient_name.strip(),
                recipient_id=recipient_id.strip(),
                signature_data=signature_data.strip(),
                proof_photo=proof_photo,
            )

            dispatch_locked.status = DispatchStatus.ENTREGADO
            dispatch_locked.delivered_at = now
            dispatch_locked.save(update_fields=["status", "delivered_at", "updated_at"])

            # Sincronizar estado comercial del pedido
            order = dispatch_locked.order
            prev_status = order.status
            order.status = OrderStatus.ENTREGADO
            order.save(update_fields=["status", "updated_at"])

            if user:
                OrderStatusHistory.objects.create(
                    order=order,
                    previous_status=prev_status,
                    new_status=order.status,
                    changed_by=user,
                    reason=f"Pedido entregado conforme a {recipient_name} ({recipient_id}). Firma digital registrada.",
                )

            # Si todas las paradas de la ruta fueron entregadas, marcar ruta como completada
            if dispatch_locked.route:
                route = dispatch_locked.route
                pending_count = route.dispatches.exclude(status=DispatchStatus.ENTREGADO).count()
                if pending_count == 0:
                    route.status = RouteStatus.COMPLETADA
                    route.save(update_fields=["status", "updated_at"])

            return proof
