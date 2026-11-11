"""
Capa de servicios para Recetas y Bill of Materials (BOM) en Dulce Arte.
Calcula insumos requeridos, conversión de unidades, factores de merma y costeo estimado.
"""

from decimal import Decimal
from typing import Dict, List
from django.core.exceptions import ValidationError
from apps.core.exceptions import BusinessLogicException
from apps.inventory.models import Supply
from apps.recipes.models import Product, Recipe, RecipeIngredient


class RecipeService:
    """
    Servicio de cálculo de Bill of Materials (BOM) y estimación de costos.
    """

    @staticmethod
    def calculate_bom_for_product(product: Product, quantity: int = 1) -> List[Dict]:
        """
        Calcula el desglose de insumos necesarios para producir una cantidad dada de un producto.
        Retorna lista de diccionarios con insumo, cantidad requerida, unidad base y costo estimado.
        """
        if not hasattr(product, "recipe") or not product.recipe:
            raise BusinessLogicException(
                f"El producto '{product.name}' ({product.code}) no tiene una receta técnica (BOM) configurada."
            )

        recipe: Recipe = product.recipe
        if recipe.yield_portions <= 0:
            raise BusinessLogicException(f"La receta '{recipe.name}' tiene un rendimiento inválido (menor o igual a cero).")

        # Factor multiplicador según porciones que rinde la receta base
        factor_rendimiento = Decimal(quantity) / Decimal(recipe.yield_portions)
        bom_items = []

        for item in recipe.ingredients.select_related("supply", "unit", "supply__unit_of_measure"):
            # Cantidad efectiva considerando el factor de merma
            effective_qty = item.get_effective_quantity() * factor_rendimiento
            # Convertir a la unidad base del insumo en inventario
            base_qty = item.unit.convert_to(effective_qty, item.supply.unit_of_measure)
            estimated_cost = base_qty * item.supply.cost_per_unit

            bom_items.append({
                "supply_id": str(item.supply.id),
                "supply_sku": item.supply.sku,
                "supply_name": item.supply.name,
                "supply_object": item.supply,
                "quantity_required_recipe": round(item.quantity_required * factor_rendimiento, 3),
                "recipe_unit_code": item.unit.code,
                "waste_percentage": float(item.waste_percentage),
                "base_quantity_needed": round(base_qty, 3),
                "base_unit_code": item.supply.unit_of_measure.code,
                "cost_per_unit": item.supply.cost_per_unit,
                "estimated_cost": round(estimated_cost, 2),
                "current_stock": item.supply.current_stock,
                "is_sufficient": item.supply.current_stock >= base_qty,
            })

        return bom_items

    @classmethod
    def calculate_total_bom_for_order(cls, order) -> Dict[str, Dict]:
        """
        Consolida los insumos totales necesarios para todos los ítems de un pedido.
        Agrupa insumos repetidos sumando sus cantidades base requeridas.
        """
        consolidated: Dict[str, Dict] = {}

        for order_item in order.items.select_related("product", "product__recipe"):
            product = order_item.product
            # Si no tiene receta, omitir o lanzar advertencia si no tiene insumos configurados
            if not hasattr(product, "recipe") or not product.recipe:
                continue

            product_bom = cls.calculate_bom_for_product(product, quantity=order_item.quantity)
            for entry in product_bom:
                supply_id = entry["supply_id"]
                if supply_id in consolidated:
                    consolidated[supply_id]["base_quantity_needed"] += entry["base_quantity_needed"]
                    consolidated[supply_id]["estimated_cost"] += entry["estimated_cost"]
                    consolidated[supply_id]["is_sufficient"] = (
                        consolidated[supply_id]["current_stock"] >= consolidated[supply_id]["base_quantity_needed"]
                    )
                else:
                    consolidated[supply_id] = entry.copy()

        return consolidated
