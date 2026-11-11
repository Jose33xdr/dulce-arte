"""
URLs de la API REST para el Dashboard - Dulce Arte.
"""

from django.urls import path

from .views import DashboardMetricsView

urlpatterns = [
    path("metrics/", DashboardMetricsView.as_view(), name="dashboard-metrics"),
]
