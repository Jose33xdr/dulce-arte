"""
Rutas API de autenticación y sesión.
"""

from django.urls import path
from .views import CurrentUserAPIView, LoginAPIView, LogoutAPIView

urlpatterns = [
    path("login/", LoginAPIView.as_view(), name="api_login"),
    path("logout/", LogoutAPIView.as_view(), name="api_logout"),
    path("me/", CurrentUserAPIView.as_view(), name="api_me"),
]
