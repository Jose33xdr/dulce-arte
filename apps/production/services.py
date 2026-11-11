"""
Capa de servicios de producción y cocina para Dulce Arte.
Orquesta las transiciones del tablero Kanban, el consumo atómico de insumos y el control de calidad.
"""

from django.db import transaction
from django.utils import timezone
from apps.core.exceptions import BusinessLogicException, InvalidStateTransitionException
from apps.inventory.services import InventoryService
from apps.orders.models import OrderStatus, OrderStatusHistory
from apps.production.models import KanbanStage, ProductionOrder, QualityCheck, QualityResult


class ProductionService:
    """
    Servicio de control de cocina, etapas Kanban y aseguramiento de calidad.
    """

    VALID_TRANSITIONS = {
        KanbanStage.RECIBIDO: [KanbanStage.EN_PREPARACION],
        KanbanStage.EN_PREPARACION: [KanbanStage.HORNEADO_DECORADO],
        KanbanStage.HORNEADO_DECORADO: [KanbanStage.CONTROL_CALIDAD],
        KanbanStage.CONTROL_CALIDAD: [KanbanStage.LISTO],
        KanbanStage.LISTO: [],
    }

    @classmethod
    def transition_stage(
        cls,
        production_order: ProductionOrder,
        target_stage: str,
        user,
        notes: str = "",
    ) -> ProductionOrder:
        """
        Ejecuta la transición de etapa en el tablero Kanban aplicando validaciones de negocio:
        - Al entrar a EN_PREPARACION: descuenta inventario BOM con bloqueo pesimista.
        - Al entrar a LISTO: exige control de calidad previamente APROBADO.
        - Sincroniza el estado comercial del pedido.
        """
        with transaction.atomic():
            prod_order = (
                # assigned_cook es opcional: bloquear solo la orden evita que
                # PostgreSQL intente aplicar FOR UPDATE al lado nullable del JOIN.
                ProductionOrder.objects.select_for_update(of=("self",))
                .select_related("order", "assigned_cook")
                .get(id=production_order.id)
            )

            current_stage = prod_order.kanban_stage

            # Validar flujo secuencial permitido
            allowed = cls.VALID_TRANSITIONS.get(current_stage, [])
            if target_stage not in allowed:
                raise InvalidStateTransitionException(
                    f"Transición Kanban inválida: No se puede avanzar de '{prod_order.get_kanban_stage_display()}' "
                    f"a '{KanbanStage(target_stage).label}'."
                )

            # Regla de Negocio 1: Consumo de insumos al ingresar a EN_PREPARACION
            if target_stage == KanbanStage.EN_PREPARACION:
                InventoryService.deduct_supplies_for_production(prod_order, user)
                if not prod_order.started_at:
                    prod_order.started_at = timezone.now()

                # Sincronizar estado comercial del pedido
                order = prod_order.order
                if order.status != OrderStatus.EN_PRODUCCION:
                    prev_status = order.status
                    order.status = OrderStatus.EN_PRODUCCION
                    order.save(update_fields=["status", "updated_at"])
                    OrderStatusHistory.objects.create(
                        order=order,
                        previous_status=prev_status,
                        new_status=order.status,
                        changed_by=user,
                        reason="Orden ingresó a etapa de preparación en cocina.",
                    )

            # Regla de Negocio 2: Control de Calidad aprobado para marcar como LISTO
            elif target_stage == KanbanStage.LISTO:
                if not hasattr(prod_order, "quality_check") or prod_order.quality_check.result != QualityResult.APROBADO:
                    raise BusinessLogicException(
                        f"No es posible marcar la orden '{prod_order.production_code}' como LISTO: "
                        f"Se exige registrar previamente un control de calidad con resultado 'Aprobado'."
                    )

                if not prod_order.finished_at:
                    prod_order.finished_at = timezone.now()

                # Sincronizar estado comercial del pedido
                order = prod_order.order
                if order.status != OrderStatus.LISTO:
                    prev_status = order.status
                    order.status = OrderStatus.LISTO
                    order.save(update_fields=["status", "updated_at"])
                    OrderStatusHistory.objects.create(
                        order=order,
                        previous_status=prev_status,
                        new_status=order.status,
                        changed_by=user,
                        reason="Producción terminada y control de calidad aprobado.",
                    )

            prod_order.kanban_stage = target_stage
            if notes:
                prod_order.notes = f"{prod_order.notes}\n[{timezone.now().strftime('%d/%m %H:%M')}] {notes}".strip()
            prod_order.save(update_fields=["kanban_stage", "started_at", "finished_at", "notes", "updated_at"])

            return prod_order

    @staticmethod
    def record_quality_check(
        production_order: ProductionOrder,
        inspector_user,
        result: str,
        observations: str = "",
    ) -> QualityCheck:
        """
        Registra o actualiza el control de calidad formal de una orden de producción.
        """
        with transaction.atomic():
            qc, _ = QualityCheck.objects.update_or_create(
                production_order=production_order,
                defaults={
                    "inspected_by": inspector_user,
                    "result": result,
                    "observations": observations,
                },
            )
            return qc

    @staticmethod
    def assign_cook(production_order: ProductionOrder, cook_user) -> ProductionOrder:
        """Asigna un maestro pastelero responsable a la orden."""
        production_order.assigned_cook = cook_user
        production_order.save(update_fields=["assigned_cook", "updated_at"])
        return production_order
