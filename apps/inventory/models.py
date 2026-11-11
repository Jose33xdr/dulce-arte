"""
Modelos de inventario, unidades de medida y movimientos de stock para Dulce Arte.
Garantiza trazabilidad completa y no negatividad de stock a nivel de esquema SQL.
"""

from decimal import Decimal
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from apps.core.models import SoftDeleteModel, TimeStampedModel


class MagnitudeType(models.TextChoices):
    MASA = "MASA", "Masa (Base: Kilogramos)"
    VOLUMEN = "VOLUMEN", "Volumen (Base: Litros)"
    UNIDAD = "UNIDAD", "Unidad / Conteo (Base: Unidades)"


class UnitOfMeasure(models.Model):
    """
    Unidad de medida con soporte para conversiones consistentes entre insumos y recetas BOM.
    """

    code = models.CharField(
        max_length=10,
        primary_key=True,
        verbose_name="Código",
        help_text="Código corto (ej. KG, GR, LT, ML, UNIDAD).",
    )
    name = models.CharField(
        max_length=50,
        verbose_name="Nombre",
        help_text="Nombre descriptivo (ej. Kilogramo, Gramo).",
    )
    magnitude = models.CharField(
        max_length=15,
        choices=MagnitudeType.choices,
        default=MagnitudeType.MASA,
        verbose_name="Tipo de Magnitud",
    )
    conversion_factor = models.DecimalField(
        max_digits=12,
        decimal_places=6,
        default=Decimal("1.000000"),
        verbose_name="Factor a unidad base",
        help_text="Multiplicador para convertir esta unidad a la base del sistema (KG, LT o UNIDAD).",
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="Activa",
    )

    class Meta:
        verbose_name = "Unidad de Medida"
        verbose_name_plural = "Unidades de Medida"
        ordering = ["magnitude", "code"]

    def __str__(self):
        return f"{self.name} ({self.code})"

    def to_base_unit(self, quantity: Decimal) -> Decimal:
        """Convierte una cantidad dada a la unidad base de su magnitud."""
        return quantity * self.conversion_factor

    def convert_to(self, quantity: Decimal, target_unit: "UnitOfMeasure") -> Decimal:
        """
        Convierte una cantidad a otra unidad compatible en la misma magnitud.
        Lanza ValidationError si las unidades pertenecen a magnitudes distintas.
        """
        if self.magnitude != target_unit.magnitude:
            raise ValidationError(
                f"No se puede convertir entre magnitudes incompatibles: "
                f"{self.magnitude} ({self.code}) y {target_unit.magnitude} ({target_unit.code})."
            )
        if self.code == target_unit.code:
            return quantity

        # Convertir primero a base y luego a la unidad destino
        base_amount = self.to_base_unit(quantity)
        return base_amount / target_unit.conversion_factor


class Supply(SoftDeleteModel):
    """
    Insumo o materia prima para pastelería y repostería artesanal.
    """

    sku = models.CharField(
        max_length=30,
        unique=True,
        db_index=True,
        verbose_name="SKU / Código",
        help_text="Identificador único del insumo (ej. INS-HAR-001).",
    )
    name = models.CharField(
        max_length=120,
        db_index=True,
        verbose_name="Nombre del insumo",
    )
    unit_of_measure = models.ForeignKey(
        UnitOfMeasure,
        on_delete=models.PROTECT,
        related_name="supplies",
        verbose_name="Unidad de medida base",
    )
    current_stock = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        default=Decimal("0.000"),
        verbose_name="Stock disponible",
        help_text="Existencias reales en almacén.",
    )
    minimum_stock = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        default=Decimal("0.000"),
        verbose_name="Stock mínimo de alerta",
        help_text="Umbral para disparar alertas de reabastecimiento.",
    )
    cost_per_unit = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Costo unitario ($)",
        help_text="Costo por unidad de medida base.",
    )

    class Meta:
        verbose_name = "Insumo"
        verbose_name_plural = "Insumos"
        ordering = ["name"]
        constraints = [
            models.CheckConstraint(
                condition=Q(current_stock__gte=0),
                name="chk_supply_stock_no_negativo",
            ),
            models.CheckConstraint(
                condition=Q(minimum_stock__gte=0),
                name="chk_supply_stock_min_no_negativo",
            ),
            models.CheckConstraint(
                condition=Q(cost_per_unit__gte=0),
                name="chk_supply_costo_no_negativo",
            ),
        ]
        indexes = [
            models.Index(fields=["sku"], name="idx_supply_sku"),
            models.Index(fields=["name"], name="idx_supply_name"),
        ]

    def __str__(self):
        return f"{self.name} [{self.sku}] ({self.current_stock} {self.unit_of_measure.code})"

    @property
    def is_low_stock(self) -> bool:
        """Determina si el insumo está en nivel crítico de existencias."""
        return self.current_stock <= self.minimum_stock


class MovementType(models.TextChoices):
    ENTRADA = "ENTRADA", "Entrada / Recepción de Compra"
    SALIDA_MANUAL = "SALIDA_MANUAL", "Salida Manual Justificada"
    CONSUMO_PRODUCCION = "CONSUMO_PRODUCCION", "Consumo por Orden de Producción"
    AJUSTE_MERMA = "AJUSTE_MERMA", "Ajuste por Merma / Vencimiento"
    DEVOLUCION = "DEVOLUCION", "Devolución a Proveedor / Corrección"


class StockMovement(TimeStampedModel):
    """
    Registro inmutable de trazabilidad de movimientos de inventario.
    Conserva saldo anterior y posterior para auditoría rigurosa.
    """

    supply = models.ForeignKey(
        Supply,
        on_delete=models.PROTECT,
        related_name="movements",
        verbose_name="Insumo",
    )
    movement_type = models.CharField(
        max_length=25,
        choices=MovementType.choices,
        verbose_name="Tipo de movimiento",
        db_index=True,
    )
    quantity = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        verbose_name="Cantidad movida",
        help_text="Cantidad en la unidad de medida base del insumo.",
    )
    stock_before = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        verbose_name="Stock anterior",
    )
    stock_after = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        verbose_name="Stock posterior",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="stock_movements",
        verbose_name="Usuario responsable",
    )
    reference = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Referencia / N° Documento",
        help_text="Código de orden, factura o guía de despacho.",
    )
    notes = models.TextField(
        blank=True,
        verbose_name="Observaciones / Justificación",
    )

    class Meta:
        verbose_name = "Movimiento de Stock"
        verbose_name_plural = "Movimientos de Stock"
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(quantity__gt=0),
                name="chk_movement_cantidad_positiva",
            ),
            models.CheckConstraint(
                condition=Q(stock_before__gte=0),
                name="chk_movement_stock_before_no_negativo",
            ),
            models.CheckConstraint(
                condition=Q(stock_after__gte=0),
                name="chk_movement_stock_after_no_negativo",
            ),
        ]
        indexes = [
            models.Index(fields=["movement_type"], name="idx_movement_type"),
            models.Index(fields=["created_at"], name="idx_movement_created"),
        ]

    def __str__(self):
        return f"{self.get_movement_type_display()} - {self.supply.name} ({self.quantity} {self.supply.unit_of_measure.code})"
