"""
Permisos y autorizaciones basadas en roles (RBAC) para API REST y Vistas Web en Dulce Arte.
Garantiza que ningún actor pueda realizar mutaciones fuera de su ámbito de atribución.
"""

from functools import wraps
from django.contrib.auth.mixins import AccessMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from rest_framework import permissions
from .models import UserRole


# ==============================================================================
# PERMISOS PARA DJANGO REST FRAMEWORK (API)
# ==============================================================================

class IsAdminRole(permissions.BasePermission):
    """Permiso exclusivo para administradores."""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_admin)


class IsSalesRole(permissions.BasePermission):
    """Permiso para rol de ventas o administradores."""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_sales)


class IsKitchenRole(permissions.BasePermission):
    """Permiso para personal de cocina/pastelería o administradores."""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_kitchen)


class IsDeliveryRole(permissions.BasePermission):
    """Permiso para personal de reparto/logística o administradores."""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_delivery)


class IsAdminOrReadOnly(permissions.BasePermission):
    """Lectura para cualquier usuario autenticado, mutación exclusiva para Administradores."""

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user.is_admin


class IsSalesOrAdminOrReadOnly(permissions.BasePermission):
    """Lectura para autenticados, mutación para Ventas o Administradores."""

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user.is_sales


class IsKitchenOrAdminOrReadOnly(permissions.BasePermission):
    """Lectura para autenticados, mutación para Cocina o Administradores."""

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user.is_kitchen


# ==============================================================================
# MIXINS Y DECORADORES PARA VISTAS WEB (DJANGO TEMPLATES)
# ==============================================================================

class RoleRequiredMixin(AccessMixin):
    """
    Mixin para CBV en Django Web que restringe el acceso a uno o más roles.
    """

    allowed_roles = []

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()

        if request.user.is_superuser or request.user.role == UserRole.ADMIN:
            return super().dispatch(request, *args, **kwargs)

        if request.user.role not in self.allowed_roles:
            raise PermissionDenied("No tienes permisos suficientes para acceder a esta vista.")

        return super().dispatch(request, *args, **kwargs)


def role_required(*allowed_roles):
    """
    Decorador para FBV que restringe el acceso según el rol del usuario autenticado.
    """

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect("login")

            if request.user.is_superuser or request.user.role == UserRole.ADMIN:
                return view_func(request, *args, **kwargs)

            if request.user.role not in allowed_roles:
                raise PermissionDenied("No tienes permisos suficientes para acceder a este recurso.")

            return view_func(request, *args, **kwargs)

        return _wrapped_view

    return decorator
