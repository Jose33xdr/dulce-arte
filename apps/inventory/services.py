"""
Capa de servicios de inventario para Dulce Arte.
Maneja entradas, salidas por merma, validación de disponibilidad y consumo atómico con bloqueo pesimista.
"""

import uuid
from decimal import Decimal
from typing import Dict, List
from django.db import transaction
from apps.core.exceptions import (
    BusinessLogicException,
    InsufficientStockException,
    StockAlreadyConsumedException,
)
from apps.inventory.models import MovementType, StockMovement, Supply
from apps.recipes.services import RecipeService


class InventoryService:
    """
    Servicio de control de existencias, trazabilidad y consumo transaccional.
    """

    @staticmethod
    def register_entry(
        supply: Supply,
        quantity: Decimal,
        user,
        reference: str = "",
        notes: str = "",
    ) -> StockMovement:
        """
        Registra una entrada de insumos (compra o reposición) con transacción atómica.
        """
        qty = Decimal(str(quantity))
        if qty <= Decimal("0"):
            raise BusinessLogicException("La cantidad de entrada debe ser estrictamente mayor a cero.")

        with transaction.atomic():
            supply_locked = Supply.objects.select_for_update().get(id=supply.id)
            stock_before = supply_locked.current_stock
            stock_after = stock_before + qty

            supply_locked.current_stock = stock_after
            supply_locked.save(update_fields=["current_stock", "updated_at"])

            movement = StockMovement.objects.create(
                supply=supply_locked,
                movement_type=MovementType.ENTRADA,
                quantity=qty,
                stock_before=stock_before,
                stock_after=stock_after,
                user=user,
                reference=reference,
                notes=notes,
            )
            return movement

    @staticmethod
    def register_waste(
        supply: Supply,
        quantity: Decimal,
        user,
        reference: str = "",
        notes: str = "",
    ) -> StockMovement:
        """
        Registra una merma o desperdicio justificado de insumo.
        """
        qty = Decimal(str(quantity))
        if qty <= Decimal("0"):
            raise BusinessLogicException("La cantidad de merma debe ser estrictamente mayor a cero.")

        with transaction.atomic():
            supply_locked = Supply.objects.select_for_update().get(id=supply.id)
            stock_before = supply_locked.current_stock

            if stock_before < qty:
                raise InsufficientStockException(
                    f"No es posible registrar la merma: Stock insuficiente para '{supply_locked.name}'. "
                    f"Disponible: {stock_before} {supply_locked.unit_of_measure.code}, Solicitado: {qty}."
                )

            stock_after = stock_before - qty
            supply_locked.current_stock = stock_after
            supply_locked.save(update_fields=["current_stock", "updated_at"])

            movement = StockMovement.objects.create(
                supply=supply_locked,
                movement_type=MovementType.AJUSTE_MERMA,
                quantity=qty,
                stock_before=stock_before,
                stock_after=stock_after,
                user=user,
                reference=reference,
                notes=notes,
            )
            return movement

    @staticmethod
    def check_availability_for_order(order) -> Dict:
        """
        Comprueba la disponibilidad de todos los insumos necesarios para un pedido.
        """
        consolidated = RecipeService.calculate_total_bom_for_order(order)
        items_list = list(consolidated.values())
        missing_items = [item for item in items_list if not item["is_sufficient"]]

        return {
            "order_number": order.order_number,
            "is_available": len(missing_items) == 0,
            "items": items_list,
            "missing_items": missing_items,
        }

    @classmethod
    def deduct_supplies_for_production(cls, production_order, user) -> List[StockMovement]:
        """
        Descuenta los insumos del BOM para una orden de producción.
        Garantiza:
        1. Transacción atómica completa (todo o nada).
        2. Bloqueo de filas en orden estable (select_for_update ordenado por ID) para prevenir deadlocks.
        3. Prevención estricta contra doble consumo (comprobación bloqueada de stock_consumed).
        4. Verificación previa de existencias con rollback automático si falta algún insumo.
        """
        with transaction.atomic():
            # 1. Bloquear la fila de la orden de producción
            prod_order = (
                production_order.__class__.objects.select_for_update()
                .select_related("order")
                .get(id=production_order.id)
            )

            # 2. Doble verificación del flag de seguridad
            if prod_order.stock_consumed:
                raise StockAlreadyConsumedException(
                    f"Los insumos de la orden de producción '{prod_order.production_code}' "
                    f"ya fueron descontados previamente del inventario."
                )

            # 3. Calcular insumos requeridos
            consolidated = RecipeService.calculate_total_bom_for_order(prod_order.order)
            if not consolidated:
                # Si el pedido no contiene productos con receta BOM configurada
                prod_order.stock_consumed = True
                prod_order.save(update_fields=["stock_consumed", "updated_at"])
                return []

            # 4. Bloquear los insumos en orden determinista por ID para evitar interbloqueos (deadlocks)
            supply_ids = sorted([uuid.UUID(s_id) for s_id in consolidated.keys()])
            supplies_locked = {
                str(s.id): s
                for s in Supply.objects.filter(id__in=supply_ids)
                .select_related("unit_of_measure")
                .order_by("id")
                .select_for_update()
            }

            # 5. Validar que TODOS los insumos cuenten con saldo suficiente
            missing = []
            for s_id, req in consolidated.items():
                s = supplies_locked.get(s_id)
                needed = req["base_quantity_needed"]
                if s.current_stock < needed:
                    missing.append(
                        f"'{s.name}' (requerido: {needed} {s.unit_of_measure.code}, "
                        f"disponible: {s.current_stock} {s.unit_of_measure.code})"
                    )

            if missing:
                faltantes_str = "; ".join(missing)
                raise InsufficientStockException(
                    f"Stock insuficiente para iniciar la producción '{prod_order.production_code}'. "
                    f"Insumos faltantes: {faltantes_str}."
                )

            # 6. Descontar existencias y registrar movimientos auditables
            movements = []
            for s_id, req in consolidated.items():
                s = supplies_locked[s_id]
                needed = req["base_quantity_needed"]
                stock_before = s.current_stock
                stock_after = stock_before - needed

                s.current_stock = stock_after
                s.save(update_fields=["current_stock", "updated_at"])

                mov = StockMovement.objects.create(
                    supply=s,
                    movement_type=MovementType.CONSUMO_PRODUCCION,
                    quantity=needed,
                    stock_before=stock_before,
                    stock_after=stock_after,
                    user=user,
                    reference=prod_order.production_code,
                    notes=f"Consumo automático BOM para pedido {prod_order.order.order_number}",
                )
                movements.append(mov)

            # 7. Marcar como descontado de forma irreversible
            prod_order.stock_consumed = True
            prod_order.save(update_fields=["stock_consumed", "updated_at"])

            return movements
