"""
URLs de la API REST para Despacho y Logística - Dulce Arte.
"""

from rest_framework.routers import DefaultRouter

from .views import DeliveryRouteViewSet, DispatchOrderViewSet

router = DefaultRouter()
router.register(r"routes", DeliveryRouteViewSet, basename="delivery-route")
router.register(r"dispatches", DispatchOrderViewSet, basename="dispatch-order")

urlpatterns = router.urls
