"""
Serializadores para Clientes en la API REST de Dulce Arte.
"""

from rest_framework import serializers
from apps.clients.models import Client


class ClientSerializer(serializers.ModelSerializer):
    """Serializador para CRUD de clientes."""

    class Meta:
        model = Client
        fields = [
            "id",
            "identification",
            "name",
            "email",
            "phone",
            "address",
            "notes",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
