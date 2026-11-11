"""
Capa de servicios del Dashboard administrativo para Dulce Arte.
Provee agregaciones y KPIs optimizados para la toma de decisiones.
"""

from decimal import Decimal
from django.db.models import Count, Sum
from django.utils import timezone
from apps.inventory.models import Supply
from apps.orders.models import Order, OrderStatus
from apps.production.models import KanbanStage, ProductionOrder
from apps.dispatch.models import DeliveryRoute, DispatchOrder, DispatchStatus


class DashboardService:
    """
    Servicio de analítica y métricas del panel administrativo.
    """

    @staticmethod
    def get_operational_metrics() -> dict:
        today = timezone.now().date()

        # 1. Pedidos
        orders_today = Order.objects.filter(delivery_date=today)
        orders_active = Order.objects.exclude(status__in=[OrderStatus.ENTREGADO, OrderStatus.CANCELADO])
        total_sales = Order.objects.filter(status__in=[OrderStatus.CONFIRMADO, OrderStatus.EN_PRODUCCION, OrderStatus.LISTO, OrderStatus.EN_DESPACHO, OrderStatus.ENTREGADO]).aggregate(
            total=Sum("total_amount"),
            deposits=Sum("deposit_amount"),
            balance=Sum("balance_due"),
        )

        # 2. Insumos Críticos
        all_supplies = Supply.objects.filter(is_active=True).select_related("unit_of_measure")
        critical_supplies = [s for s in all_supplies if s.is_low_stock]

        # 3. Tablero Kanban de Producción
        kanban_counts = (
            ProductionOrder.objects.values("kanban_stage")
            .annotate(total=Count("id"))
            .order_by("kanban_stage")
        )
        kanban_summary = {stage.value: 0 for stage in KanbanStage}
        for item in kanban_counts:
            kanban_summary[item["kanban_stage"]] = item["total"]

        # 4. Despachos y Rutas de Hoy
        routes_today = DeliveryRoute.objects.filter(scheduled_date=today)
        dispatches_today = DispatchOrder.objects.filter(order__delivery_date=today)
        delivered_count = dispatches_today.filter(status=DispatchStatus.ENTREGADO).count()

        return {
            "date": today.isoformat(),
            "orders": {
                "active_total": orders_active.count(),
                "scheduled_today": orders_today.count(),
                "by_status": dict(Order.objects.values("status").annotate(c=Count("id")).values_list("status", "c")),
            },
            "financial": {
                "total_sales": total_sales["total"] or Decimal("0.00"),
                "total_deposits": total_sales["deposits"] or Decimal("0.00"),
                "total_balance_due": total_sales["balance"] or Decimal("0.00"),
            },
            "inventory": {
                "total_supplies": all_supplies.count(),
                "critical_supplies_count": len(critical_supplies),
                "critical_supplies": [
                    {
                        "sku": s.sku,
                        "name": s.name,
                        "current_stock": float(s.current_stock),
                        "minimum_stock": float(s.minimum_stock),
                        "unit": s.unit_of_measure.code,
                    }
                    for s in critical_supplies[:10]
                ],
            },
            "production": {
                "kanban_summary": kanban_summary,
                "in_preparation_count": kanban_summary.get(KanbanStage.EN_PREPARACION, 0),
            },
            "dispatch": {
                "routes_today_count": routes_today.count(),
                "dispatches_today_count": dispatches_today.count(),
                "delivered_today_count": delivered_count,
            },
        }
