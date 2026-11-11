"""
Serializadores para Productos, Recetas y Bill of Materials (BOM) en la API REST de Dulce Arte.
"""

from decimal import Decimal
from django.db import transaction
from rest_framework import serializers
from apps.recipes.models import Product, Recipe, RecipeIngredient


class ProductSerializer(serializers.ModelSerializer):
    category_display = serializers.CharField(source="get_category_display", read_only=True)
    has_recipe = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id",
            "code",
            "name",
            "category",
            "category_display",
            "base_price",
            "estimated_production_minutes",
            "description",
            "has_recipe",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "has_recipe", "created_at", "updated_at"]

    def get_has_recipe(self, obj) -> bool:
        return hasattr(obj, "recipe") and obj.recipe is not None


class RecipeIngredientSerializer(serializers.ModelSerializer):
    supply_name = serializers.CharField(source="supply.name", read_only=True)
    supply_sku = serializers.CharField(source="supply.sku", read_only=True)
    unit_code = serializers.CharField(source="unit.code", read_only=True)
    base_unit_code = serializers.CharField(source="supply.unit_of_measure.code", read_only=True)

    class Meta:
        model = RecipeIngredient
        fields = [
            "id",
            "supply",
            "supply_name",
            "supply_sku",
            "quantity_required",
            "unit",
            "unit_code",
            "base_unit_code",
            "waste_percentage",
        ]


class RecipeSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_code = serializers.CharField(source="product.code", read_only=True)
    ingredients = RecipeIngredientSerializer(many=True, read_only=True)

    class Meta:
        model = Recipe
        fields = [
            "id",
            "product",
            "product_name",
            "product_code",
            "name",
            "yield_portions",
            "instructions",
            "ingredients",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class RecipeCreateUpdateSerializer(serializers.ModelSerializer):
    """Permite crear o actualizar una receta y sus ingredientes de manera anidada."""

    ingredients = RecipeIngredientSerializer(many=True, required=False)

    class Meta:
        model = Recipe
        fields = [
            "id",
            "product",
            "name",
            "yield_portions",
            "instructions",
            "ingredients",
            "is_active",
        ]

    def create(self, validated_data):
        ingredients_data = validated_data.pop("ingredients", [])
        self._validate_ingredients(ingredients_data)
        with transaction.atomic():
            recipe = Recipe.objects.create(**validated_data)
            for item in ingredients_data:
                RecipeIngredient.objects.create(recipe=recipe, **item)
        return recipe

    def update(self, instance, validated_data):
        ingredients_data = validated_data.pop("ingredients", None)
        self._validate_ingredients(ingredients_data)
        with transaction.atomic():
            for field, value in validated_data.items():
                setattr(instance, field, value)
            instance.full_clean()
            instance.save()
            if ingredients_data is not None:
                instance.ingredients.all().delete()
                for item in ingredients_data:
                    RecipeIngredient.objects.create(recipe=instance, **item)
        return instance

    @staticmethod
    def _validate_ingredients(ingredients_data):
        if ingredients_data is None:
            return
        supply_ids = [item["supply"].id for item in ingredients_data]
        if len(supply_ids) != len(set(supply_ids)):
            raise serializers.ValidationError({"ingredients": "Un insumo solo puede aparecer una vez en la receta."})
        for item in ingredients_data:
            if item["supply"].unit_of_measure.magnitude != item["unit"].magnitude:
                raise serializers.ValidationError({"ingredients": "La unidad de cada ingrediente debe tener la misma magnitud que su insumo."})
