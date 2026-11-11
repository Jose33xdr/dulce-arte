"""
Modelos de producción, tablero Kanban y control de calidad para cocina de Dulce Arte.
Permite trazar el avance de las órdenes de repostería y la deducción segura de insumos.
"""

from django.conf import settings
from django.db import models
from apps.core.models import TimeStampedModel
from apps.orders.models import Order


class KanbanStage(models.TextChoices):
    RECIBIDO = "RECIBIDO", "1. Recibido en Cocina"
    EN_PREPARACION = "EN_PREPARACION", "2. En Preparación (Masa / Rellenos)"
    HORNEADO_DECORADO = "HORNEADO_DECORADO", "3. Horneado y Decorado"
    CONTROL_CALIDAD = "CONTROL_CALIDAD", "4. Control de Calidad"
    LISTO = "LISTO", "5. Listo para Despacho"


class ProductionOrder(TimeStampedModel):
    """
    Orden de producción interna para cocina y maestros pasteleros.
    Controla el avance en el tablero Kanban y la deducción protegida de insumos.
    """

    order = models.OneToOneField(
        Order,
        on_delete=models.PROTECT,
        related_name="production_order",
        verbose_name="Pedido asociado",
    )
    production_code = models.CharField(
        max_length=30,
        unique=True,
        db_index=True,
        verbose_name="Código de Producción (OP-YYYY-XXXXX)",
    )
    kanban_stage = models.CharField(
        max_length=30,
        choices=KanbanStage.choices,
        default=KanbanStage.RECIBIDO,
        db_index=True,
        verbose_name="Etapa en Kanban",
    )
    assigned_cook = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_cooking_orders",
        verbose_name="Pastelero / Cocinero asignado",
    )
    stock_consumed = models.BooleanField(
        default=False,
        verbose_name="Stock de insumos descontado",
        help_text="Bandera de seguridad para evitar descuentos duplicados de inventario.",
    )
    started_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Fecha y hora de inicio",
    )
    finished_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Fecha y hora de término",
    )
    notes = models.TextField(
        blank=True,
        verbose_name="Observaciones de producción",
        help_text="Indicaciones especiales de horneado o tiempos de reposo.",
    )

    class Meta:
        verbose_name = "Orden de Producción"
        verbose_name_plural = "Órdenes de Producción"
        ordering = ["kanban_stage", "-created_at"]
        indexes = [
            models.Index(fields=["production_code"], name="idx_prod_code"),
            models.Index(fields=["kanban_stage"], name="idx_prod_stage"),
        ]

    def __str__(self):
        return f"{self.production_code} ({self.order.order_number}) - {self.get_kanban_stage_display()}"


class QualityResult(models.TextChoices):
    APROBADO = "APROBADO", "Aprobado (Conforme para Entrega)"
    RECHAZADO = "RECHAZADO", "Rechazado (No Cumple Estándar)"
    REQUIERE_AJUSTE = "REQUIERE_AJUSTE", "Requiere Ajuste Decorativo Menor"


class QualityCheck(TimeStampedModel):
    """
    Registro formal de control de calidad previo al empaque y despacho final.
    """

    production_order = models.OneToOneField(
        ProductionOrder,
        on_delete=models.PROTECT,
        related_name="quality_check",
        verbose_name="Orden de producción evaluada",
    )
    inspected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="inspected_quality_checks",
        verbose_name="Inspector de calidad",
    )
    result = models.CharField(
        max_length=25,
        choices=QualityResult.choices,
        default=QualityResult.APROBADO,
        verbose_name="Resultado del control",
    )
    observations = models.TextField(
        blank=True,
        verbose_name="Observaciones de calidad",
        help_text="Verificación visual del diseño, dedicatoria, peso y temperatura.",
    )

    class Meta:
        verbose_name = "Control de Calidad"
        verbose_name_plural = "Controles de Calidad"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Control Calidad {self.production_order.production_code}: {self.get_result_display()}"
