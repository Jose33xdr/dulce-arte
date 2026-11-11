"""
URLs de la API REST para Producción Kanban - Dulce Arte.
"""

from rest_framework.routers import DefaultRouter

from .views import ProductionOrderViewSet

router = DefaultRouter()
router.register(r"production", ProductionOrderViewSet, basename="production-order")

urlpatterns = router.urls
