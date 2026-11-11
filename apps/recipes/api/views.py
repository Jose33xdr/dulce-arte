"""
Vistas API REST para Productos y Recetas (BOM) en Dulce Arte.
"""

from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from apps.recipes.models import Product, Recipe
from apps.recipes.services import RecipeService
from apps.users.permissions import IsAdminOrReadOnly
from .serializers import ProductSerializer, RecipeCreateUpdateSerializer, RecipeSerializer


class ProductViewSet(viewsets.ModelViewSet):
    """
    Catálogo de productos de pastelería con consulta técnica de BOM.
    """

    queryset = Product.objects.all().order_by("category", "name")
    serializer_class = ProductSerializer
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["code", "name"]
    ordering_fields = ["name", "base_price", "category"]

    def perform_destroy(self, instance):
        instance.soft_delete()

    @action(detail=True, methods=["get"], permission_classes=[IsAuthenticated])
    def bom(self, request, pk=None):
        """Calcula el desglose de insumos (BOM) para el producto."""
        product = self.get_object()
        quantity = int(request.query_params.get("quantity", 1))
        bom_data = RecipeService.calculate_bom_for_product(product, quantity=quantity)

        # Ocultar costo unitario a no administradores
        if not request.user.is_admin:
            for item in bom_data:
                item.pop("cost_per_unit", None)
                item.pop("estimated_cost", None)
                item.pop("supply_object", None)
        else:
            for item in bom_data:
                item.pop("supply_object", None)

        return Response(
            {
                "product_code": product.code,
                "product_name": product.name,
                "quantity": quantity,
                "ingredients": bom_data,
            },
            status=status.HTTP_200_OK,
        )


class RecipeViewSet(viewsets.ModelViewSet):
    """
    CRUD de recetas técnicas (BOM).
    """

    queryset = Recipe.objects.all().select_related("product").prefetch_related("ingredients__supply", "ingredients__unit").order_by("name")
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [filters.SearchFilter]
    search_fields = ["name", "product__name", "product__code"]

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return RecipeCreateUpdateSerializer
        return RecipeSerializer

    def perform_destroy(self, instance):
        instance.soft_delete()
