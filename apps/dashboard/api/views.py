"""
Vistas API REST para el Dashboard Administrativo - Dulce Arte.
Expone métricas operacionales consolidadas para el panel de control.
"""

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.dashboard.services import DashboardService
from apps.users.permissions import IsAdminRole


class DashboardMetricsView(APIView):
    """
    Retorna métricas operacionales en tiempo real del negocio.
    Solo accesible para administradores.
    """

    permission_classes = [IsAdminRole]

    def get(self, request, *args, **kwargs):
        metrics = DashboardService.get_operational_metrics()
        return Response(metrics)
