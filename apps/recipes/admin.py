"""
Administración avanzada para Productos, Recetas y Bill of Materials (BOM) en Dulce Arte.
Permite configurar insumos de manera tabular directamente desde la receta.
"""

from django.contrib import admin
from django.utils.html import format_html
from .models import Product, Recipe, RecipeIngredient


class RecipeIngredientInline(admin.TabularInline):
    """Edición tabular de ingredientes dentro de la receta."""

    model = RecipeIngredient
    extra = 1
    autocomplete_fields = ["supply"]
    fields = ("supply", "quantity_required", "unit", "waste_percentage")
    ordering = ["supply__name"]


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "name",
        "category",
        "base_price",
        "estimated_production_minutes",
        "has_recipe_badge",
        "is_active",
    )
    list_filter = ("category", "is_active")
    search_fields = ("code", "name")
    ordering = ["category", "name"]
    readonly_fields = ("created_at", "updated_at", "deleted_at")

    fieldsets = (
        (
            "Información del Producto",
            {
                "fields": ("code", "name", "category", "is_active"),
            },
        ),
        (
            "Costos y Tiempos",
            {
                "fields": ("base_price", "estimated_production_minutes", "description"),
            },
        ),
        (
            "Auditoría",
            {
                "classes": ("collapse",),
                "fields": ("created_at", "updated_at", "deleted_at"),
            },
        ),
    )

    @admin.display(description="Receta BOM")
    def has_recipe_badge(self, obj):
        if hasattr(obj, "recipe") and obj.recipe:
            return format_html(
                '<span style="background-color: #DCEBDD; color: #2d5a33; padding: 2px 7px; border-radius: 9999px; font-size: 11px; font-weight: bold;">Configurada</span>'
            )
        return format_html(
            '<span style="background-color: #FEF3C7; color: #92400E; padding: 2px 7px; border-radius: 9999px; font-size: 11px; font-weight: bold;">Sin Receta</span>'
        )


@admin.register(Recipe)
class RecipeAdmin(admin.ModelAdmin):
    list_display = ("name", "product", "yield_portions", "ingredients_count", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "product__name", "product__code")
    inlines = [RecipeIngredientInline]
    ordering = ["name"]
    list_select_related = ("product",)

    @admin.display(description="Total Insumos")
    def ingredients_count(self, obj):
        return obj.ingredients.count()
