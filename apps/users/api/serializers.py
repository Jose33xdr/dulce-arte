"""
Serializadores DRF para autenticación y gestión de usuarios.
"""

from rest_framework import serializers
from apps.users.models import User


class UserSerializer(serializers.ModelSerializer):
    """Serializador de lectura y perfil de usuario."""

    role_display = serializers.CharField(source="get_role_display", read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "role",
            "role_display",
            "phone",
            "identification",
            "is_active",
        ]
        read_only_fields = ["id", "role_display", "is_active"]


class LoginSerializer(serializers.Serializer):
    """Serializador para validación de credenciales en login."""

    username = serializers.CharField(required=True)
    password = serializers.CharField(required=True, write_only=True)
