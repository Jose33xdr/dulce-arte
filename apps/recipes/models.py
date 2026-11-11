"""
Modelos de productos, recetas y Bill of Materials (BOM) para Dulce Arte.
Permite definir insumos requeridos, cantidades, porcentajes de merma y unidades compatibles.
"""

from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from apps.core.models import SoftDeleteModel, TimeStampedModel
from apps.inventory.models import Supply, UnitOfMeasure


class ProductCategory(models.TextChoices):
    TORTA_TRADICIONAL = "TORTA_TRADICIONAL", "Torta Tradicional"
    PASTEL_FONDANT = "PASTEL_FONDANT", "Pastel Fondant / Personalizado"
    REPOSTERIA_INDIVIDUAL = "REPOSTERIA_INDIVIDUAL", "Repostería Individual"
    COCTELERIA = "COCTELERIA", "Coctelería Dulce"


class Product(SoftDeleteModel):
    """
    Producto terminado o base de pastelería artesanal.
    """

    code = models.CharField(
        max_length=30,
        unique=True,
        db_index=True,
        verbose_name="Código de Producto",
        help_text="Código institucional (ej. PRD-TOR-001).",
    )
    name = models.CharField(
        max_length=150,
        verbose_name="Nombre del producto",
    )
    category = models.CharField(
        max_length=30,
        choices=ProductCategory.choices,
        default=ProductCategory.TORTA_TRADICIONAL,
        verbose_name="Categoría",
    )
    base_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Precio base ($)",
        help_text="Precio de venta sugerido para tamaño estándar.",
    )
    estimated_production_minutes = models.PositiveIntegerField(
        default=60,
        verbose_name="Tiempo estimado de producción (min)",
        help_text="Tiempo total de preparación, horneado y decorado.",
    )
    description = models.TextField(
        blank=True,
        verbose_name="Descripción",
    )

    class Meta:
        verbose_name = "Producto"
        verbose_name_plural = "Productos"
        ordering = ["category", "name"]
        constraints = [
            models.CheckConstraint(
                condition=Q(base_price__gte=0),
                name="chk_product_base_price_no_negativo",
            ),
        ]
        indexes = [
            models.Index(fields=["code"], name="idx_product_code"),
            models.Index(fields=["category"], name="idx_product_category"),
        ]

    def __str__(self):
        return f"{self.name} [{self.code}] (${self.base_price})"


class Recipe(SoftDeleteModel):
    """
    Receta técnica o Bill of Materials (BOM) asociada a un producto base.
    """

    product = models.OneToOneField(
        Product,
        on_delete=models.PROTECT,
        related_name="recipe",
        verbose_name="Producto asociado",
    )
    name = models.CharField(
        max_length=150,
        verbose_name="Nombre de la receta",
    )
    yield_portions = models.PositiveIntegerField(
        default=1,
        verbose_name="Rendimiento estándar",
        help_text="Cantidad de porciones o unidades que rinde la receta base.",
    )
    instructions = models.TextField(
        blank=True,
        verbose_name="Instrucciones y observaciones técnicas",
    )

    class Meta:
        verbose_name = "Receta (BOM)"
        verbose_name_plural = "Recetas (BOM)"
        ordering = ["name"]
        constraints = [
            models.CheckConstraint(
                condition=Q(yield_portions__gt=0),
                name="chk_recipe_yield_mayor_cero",
            ),
        ]

    def __str__(self):
        return f"Receta: {self.name} (Rinde {self.yield_portions} porciones)"


class RecipeIngredient(TimeStampedModel):
    """
    Ingrediente componente de una receta (BOM).
    Define la relación entre receta e insumo con conversión de unidades y merma.
    """

    recipe = models.ForeignKey(
        Recipe,
        on_delete=models.CASCADE,
        related_name="ingredients",
        verbose_name="Receta",
    )
    supply = models.ForeignKey(
        Supply,
        on_delete=models.PROTECT,
        related_name="recipe_usages",
        verbose_name="Insumo",
    )
    quantity_required = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        verbose_name="Cantidad requerida",
        help_text="Cantidad en la unidad de medida especificada.",
    )
    unit = models.ForeignKey(
        UnitOfMeasure,
        on_delete=models.PROTECT,
        related_name="recipe_ingredients",
        verbose_name="Unidad de medida",
    )
    waste_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Porcentaje de merma (%)",
        help_text="Factor de pérdida en manipulación o cocción (0 - 100%).",
    )

    class Meta:
        verbose_name = "Ingrediente de Receta"
        verbose_name_plural = "Ingredientes de Receta"
        ordering = ["supply__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["recipe", "supply"],
                name="unique_recipe_supply_ingredient",
            ),
            models.CheckConstraint(
                condition=Q(quantity_required__gt=0),
                name="chk_ingredient_cantidad_positiva",
            ),
            models.CheckConstraint(
                condition=Q(waste_percentage__gte=0) & Q(waste_percentage__lte=100),
                name="chk_ingredient_merma_valida",
            ),
        ]

    def clean(self):
        super().clean()
        # Validación de unidades compatibles entre receta e insumo
        if self.unit and self.supply and self.supply.unit_of_measure:
            if self.unit.magnitude != self.supply.unit_of_measure.magnitude:
                raise ValidationError(
                    f"Incompatibilidad de magnitud: La unidad '{self.unit.name}' ({self.unit.get_magnitude_display()}) "
                    f"no es compatible con el insumo '{self.supply.name}' que usa "
                    f"'{self.supply.unit_of_measure.name}' ({self.supply.unit_of_measure.get_magnitude_display()})."
                )

    def get_effective_quantity(self) -> Decimal:
        """Calcula la cantidad bruta necesaria considerando el porcentaje de merma."""
        factor_merma = Decimal("1.000") + (self.waste_percentage / Decimal("100.00"))
        return self.quantity_required * factor_merma

    def get_base_unit_quantity(self) -> Decimal:
        """
        Retorna la cantidad efectiva convertida a la unidad de medida base del insumo en inventario.
        """
        effective = self.get_effective_quantity()
        return self.unit.convert_to(effective, self.supply.unit_of_measure)

    def __str__(self):
        return f"{self.supply.name}: {self.quantity_required} {self.unit.code} (+{self.waste_percentage}% merma)"
