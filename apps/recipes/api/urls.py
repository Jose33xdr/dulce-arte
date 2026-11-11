"""
Enrutador de rutas API para Productos y Recetas.
"""

from rest_framework.routers import DefaultRouter
from .views import ProductViewSet, RecipeViewSet

router = DefaultRouter()
router.register(r"products", ProductViewSet, basename="product")
router.register(r"recipes", RecipeViewSet, basename="recipe")

urlpatterns = router.urls
