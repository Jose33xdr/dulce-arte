"""
Capa de servicios de pedidos y cotizaciones para Dulce Arte.
Maneja la creación, personalización, control financiero, confirmación y ciclo de vida comercial.
"""

from decimal import Decimal
from typing import Dict, List, Optional
from django.db import transaction
from django.utils import timezone
from apps.core.exceptions import BusinessLogicException, InvalidStateTransitionException
from apps.core.utils import generate_order_code, generate_production_code
from apps.orders.models import DeliveryType, Order, OrderItem, OrderStatus, OrderStatusHistory
from apps.production.models import KanbanStage, ProductionOrder
from apps.dispatch.models import DispatchOrder, DispatchStatus


class OrderService:
    """
    Servicio de orquestación de pedidos, cotizaciones y estados comerciales.
    """

    @classmethod
    def create_order(
        cls,
        client,
        delivery_date,
        delivery_time,
        items_data: List[Dict],
        delivery_type: str = DeliveryType.RETIRO_TIENDA,
        delivery_address: str = "",
        deposit_amount: Decimal = Decimal("0.00"),
        custom_design_notes: str = "",
        user=None,
        status: str = OrderStatus.COTIZACION,
    ) -> Order:
        """
        Crea un nuevo pedido o cotización con sus ítems personalizados y auditoría.
        """
        # Validación de fecha de entrega
        if delivery_date < timezone.now().date():
            raise BusinessLogicException("La fecha de entrega programada no puede ser anterior al día de hoy.")

        if not items_data:
            raise BusinessLogicException("El pedido debe contener al menos un producto o ítem.")

        with transaction.atomic():
            # Generar código correlativo único DA-YYYY-XXXXX
            current_year = timezone.now().year
            order_count = Order.objects.filter(created_at__year=current_year).count() + 1
            order_number = generate_order_code(order_count)
            while Order.objects.filter(order_number=order_number).exists():
                order_count += 1
                order_number = generate_order_code(order_count)

            # Calcular el total antes del primer INSERT. La restricción SQL exige
            # que un abono nunca supere el total, incluso durante la creación.
            prepared_items = []
            total_calculated = Decimal("0.00")
            for item_info in items_data:
                product = item_info["product"]
                quantity = int(item_info.get("quantity", 1))
                unit_price = Decimal(str(item_info.get("unit_price", product.base_price)))
                subtotal = Decimal(quantity) * unit_price
                total_calculated += subtotal
                prepared_items.append((item_info, product, quantity, unit_price, subtotal))

            deposit = Decimal(str(deposit_amount))
            if deposit > total_calculated:
                raise BusinessLogicException("El abono no puede superar el monto total del pedido.")

            order = Order(
                order_number=order_number,
                client=client,
                status=status,
                delivery_date=delivery_date,
                delivery_time=delivery_time,
                delivery_type=delivery_type,
                delivery_address=delivery_address,
                total_amount=total_calculated,
                deposit_amount=deposit,
                balance_due=total_calculated - deposit,
                custom_design_notes=custom_design_notes,
            )
            order.save()

            for item_info, product, quantity, unit_price, subtotal in prepared_items:
                OrderItem.objects.create(
                    order=order,
                    product=product,
                    quantity=quantity,
                    unit_price=unit_price,
                    subtotal=subtotal,
                    cake_size=item_info.get("cake_size", ""),
                    flavor_sponge=item_info.get("flavor_sponge", ""),
                    flavor_filling=item_info.get("flavor_filling", ""),
                    flavor_cover=item_info.get("flavor_cover", ""),
                    custom_dedication=item_info.get("custom_dedication", ""),
                    customizations=item_info.get("customizations", ""),
                )

            # Historial inicial
            if user:
                OrderStatusHistory.objects.create(
                    order=order,
                    previous_status="NUEVO",
                    new_status=order.status,
                    changed_by=user,
                    reason="Creación y registro del pedido en el sistema.",
                )

            # Si se crea directamente en estado CONFIRMADO, emitir orden de producción
            if status == OrderStatus.CONFIRMADO:
                cls._setup_production_and_dispatch(order)

            return order

    @classmethod
    def confirm_order(
        cls,
        order: Order,
        deposit_amount: Optional[Decimal] = None,
        user=None,
        reason: str = "Confirmación de cotización y abono registrado.",
    ) -> Order:
        """
        Confirma una cotización previa, actualiza el abono y genera la orden de producción.
        """
        with transaction.atomic():
            order_locked = Order.objects.select_for_update().get(id=order.id)

            if order_locked.status != OrderStatus.COTIZACION:
                raise InvalidStateTransitionException(
                    f"Solo pedidos en estado COTIZACION pueden ser confirmados. Estado actual: '{order_locked.get_status_display()}'."
                )

            previous_status = order_locked.status
            if deposit_amount is not None:
                abono = Decimal(str(deposit_amount))
                if abono > order_locked.total_amount:
                    raise BusinessLogicException("El abono no puede superar el monto total del pedido.")
                order_locked.deposit_amount = abono
                order_locked.balance_due = order_locked.total_amount - abono

            order_locked.status = OrderStatus.CONFIRMADO
            order_locked.save(update_fields=["status", "deposit_amount", "balance_due", "updated_at"])

            if user:
                OrderStatusHistory.objects.create(
                    order=order_locked,
                    previous_status=previous_status,
                    new_status=order_locked.status,
                    changed_by=user,
                    reason=reason,
                )

            # Generar orden de producción y despacho
            cls._setup_production_and_dispatch(order_locked)

            return order_locked

    @classmethod
    def cancel_order(
        cls,
        order: Order,
        user,
        reason: str = "Cancelación de pedido solicitada.",
    ) -> Order:
        """
        Cancela un pedido registrando el motivo en la bitácora histórica.
        """
        with transaction.atomic():
            order_locked = Order.objects.select_for_update().get(id=order.id)

            if order_locked.status in [OrderStatus.ENTREGADO, OrderStatus.CANCELADO]:
                raise InvalidStateTransitionException(
                    f"No es posible cancelar un pedido en estado '{order_locked.get_status_display()}'."
                )

            previous_status = order_locked.status
            order_locked.status = OrderStatus.CANCELADO
            order_locked.save(update_fields=["status", "updated_at"])

            OrderStatusHistory.objects.create(
                order=order_locked,
                previous_status=previous_status,
                new_status=order_locked.status,
                changed_by=user,
                reason=reason,
            )

            return order_locked

    @classmethod
    def _setup_production_and_dispatch(cls, order: Order):
        """
        Genera la Orden de Producción para cocina y el Despacho si aplica entrega a domicilio.
        """
        # 1. Crear Orden de Producción si no existe
        if not hasattr(order, "production_order"):
            current_year = timezone.now().year
            prod_count = ProductionOrder.objects.filter(created_at__year=current_year).count() + 1
            prod_code = generate_production_code(prod_count)
            while ProductionOrder.objects.filter(production_code=prod_code).exists():
                prod_count += 1
                prod_code = generate_production_code(prod_count)

            ProductionOrder.objects.create(
                order=order,
                production_code=prod_code,
                kanban_stage=KanbanStage.RECIBIDO,
                stock_consumed=False,
            )

        # 2. Crear Despacho si es entrega a domicilio y no existe
        if order.delivery_type == DeliveryType.DESPACHO_DOMICILIO and not hasattr(order, "dispatch_order"):
            DispatchOrder.objects.create(
                order=order,
                status=DispatchStatus.PENDIENTE,
                stop_order=1,
            )
