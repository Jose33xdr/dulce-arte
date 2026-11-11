"""
Rutas web del Dashboard principal.
"""

from django.urls import path
from .views import (
    ClientsView,
    DashboardHomeView,
    DispatchView,
    InventoryView,
    OrdersView,
    ProductionView,
    RecipesView,
)

app_name = "dashboard"

urlpatterns = [
    path("", DashboardHomeView.as_view(), name="home"),
    path("clientes/", ClientsView.as_view(), name="clients"),
    path("pedidos/", OrdersView.as_view(), name="orders"),
    path("inventario/", InventoryView.as_view(), name="inventory"),
    path("recetas/", RecipesView.as_view(), name="recipes"),
    path("produccion/", ProductionView.as_view(), name="production"),
    path("despachos/", DispatchView.as_view(), name="dispatch"),
]
