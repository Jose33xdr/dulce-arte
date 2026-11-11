"""
Vistas web de autenticación basada en sesiones para Dulce Arte.
"""

from django.contrib.auth import views as auth_views
from django.urls import reverse_lazy


class CustomLoginView(auth_views.LoginView):
    """Vista de inicio de sesión con plantilla corporativa Dulce Arte."""
    template_name = "users/login.html"
    redirect_authenticated_user = True

    def get_success_url(self):
        return reverse_lazy("dashboard:home")


class CustomLogoutView(auth_views.LogoutView):
    """Vista de cierre de sesión."""
    next_page = reverse_lazy("login")
