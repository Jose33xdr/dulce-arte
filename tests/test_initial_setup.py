"""
Pruebas de verificación inicial para la Fase 2 de Dulce Arte.
Comprueba conexión a BD, modelos de usuario con roles, vistas web y API REST.
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.db import connection
from apps.users.models import User, UserRole


class InitialSetupVerificationTests(TestCase):
    def setUp(self):
        self.client = Client()
        # Usuario administrador para pruebas
        self.admin_user = User.objects.create_user(
            username="admin_test",
            email="admin@dulcearte.cl",
            password="SecurePassword123!",
            role=UserRole.ADMIN,
            is_staff=True,
            is_superuser=True,
        )
        # Usuario de ventas
        self.sales_user = User.objects.create_user(
            username="ventas_test",
            email="ventas@dulcearte.cl",
            password="SecurePassword123!",
            role=UserRole.VENTAS,
        )

    def test_database_connection(self):
        """Verifica que la base de datos PostgreSQL responda consultas correctamente."""
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1;")
            row = cursor.fetchone()
        self.assertEqual(row[0], 1)

    def test_custom_user_roles(self):
        """Verifica la asignación y propiedades de roles en el modelo personalizado."""
        self.assertTrue(self.admin_user.is_admin)
        self.assertTrue(self.sales_user.is_sales)
        self.assertFalse(self.sales_user.is_admin)
        self.assertFalse(self.sales_user.is_kitchen)
        self.assertFalse(self.sales_user.is_delivery)

    def test_admin_login_page_status(self):
        """Verifica que el Django Admin esté accesible."""
        response = self.client.get("/admin/login/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Dulce Arte")

    def test_web_login_page_status(self):
        """Verifica que la página de login web personalizada esté accesible."""
        response = self.client.get(reverse("login"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Dulce Arte")

    def test_dashboard_redirects_unauthenticated(self):
        """Verifica que el dashboard redirija a usuarios anónimos al login."""
        response = self.client.get(reverse("dashboard:home"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/auth/login/", response.url)

    def test_dashboard_accessible_when_authenticated(self):
        """Verifica que un usuario autenticado pueda visualizar el dashboard."""
        self.client.login(username="admin_test", password="SecurePassword123!")
        response = self.client.get(reverse("dashboard:home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Panel de Control Operativo")

    def test_api_login_success(self):
        """Verifica inicio de sesión mediante el endpoint REST v1."""
        response = self.client.post(
            reverse("api_login"),
            data={"username": "ventas_test", "password": "SecurePassword123!"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        json_data = response.json()
        self.assertIn("user", json_data)
        self.assertEqual(json_data["user"]["role"], "VENTAS")

    def test_api_login_invalid_credentials(self):
        """Verifica rechazo con HTTP 401 para credenciales erróneas."""
        response = self.client.post(
            reverse("api_login"),
            data={"username": "ventas_test", "password": "WrongPassword"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)
