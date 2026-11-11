"""
Vistas API REST para Clientes en Dulce Arte.
"""

from rest_framework import filters, viewsets
from apps.clients.models import Client
from apps.users.permissions import IsSalesOrAdminOrReadOnly
from .serializers import ClientSerializer


class ClientViewSet(viewsets.ModelViewSet):
    """
    CRUD completo de clientes con búsqueda, ordenación y eliminación lógica protegida.
    """

    queryset = Client.objects.all().order_by("name")
    serializer_class = ClientSerializer
    permission_classes = [IsSalesOrAdminOrReadOnly]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["identification", "name", "email", "phone"]
    ordering_fields = ["name", "created_at"]

    def perform_destroy(self, instance):
        # En lugar de eliminar físicamente, aplicar soft_delete protegida
        instance.soft_delete()
