"""
Enrutador de rutas API para Inventario.
"""

from rest_framework.routers import DefaultRouter
from .views import StockMovementViewSet, SupplyViewSet, UnitOfMeasureViewSet

router = DefaultRouter()
router.register(r"units", UnitOfMeasureViewSet, basename="unit")
router.register(r"supplies", SupplyViewSet, basename="supply")
router.register(r"movements", StockMovementViewSet, basename="movement")

urlpatterns = router.urls
