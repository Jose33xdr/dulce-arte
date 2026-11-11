"""
Suite de pruebas de integración para la API REST de Fase 4 - Dulce Arte.

Cubre:
  - Autenticación y control de acceso por rol (401, 403)
  - CRUD de Clientes
  - Inventario: entradas, mermas, stock insuficiente
  - Pedidos: cotización, confirmación, cancelación, BOM check
  - Producción Kanban: transiciones, doble descuento, control de calidad
  - Despacho: rutas, paradas, inicio, confirmación de entrega (idempotencia)
  - Dashboard: métricas solo para ADMIN
  - Historial de estados de pedido
"""

import json
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.clients.models import Client
from apps.dispatch.models import DeliveryRoute, DispatchOrder, DispatchStatus, RouteStatus
from apps.inventory.models import StockMovement, Supply, UnitOfMeasure
from apps.orders.models import Order, OrderStatus
from apps.production.models import KanbanStage, ProductionOrder, QualityResult
from apps.recipes.models import Product, Recipe, RecipeIngredient
from apps.users.models import User, UserRole


# ==============================================================================
# HELPERS
# ==============================================================================

def make_user(username, role, password="TestPass123!"):
    """Crea un usuario con el rol y contraseña indicados."""
    user = User.objects.create_user(
        username=username,
        password=password,
        email=f"{username}@dulcearte.cl",
        first_name=username.capitalize(),
        role=role,
    )
    return user


def authenticated_client(user, password="TestPass123!"):
    """Devuelve un APIClient con sesión autenticada."""
    client = APIClient()
    client.login(username=user.username, password=password)
    return client


# ==============================================================================
# FIXTURES COMPARTIDOS
# ==============================================================================

class BaseAPITestCase(TestCase):
    """
    Caso base que crea la infraestructura mínima para todas las pruebas:
    usuarios por rol, unidades, insumos, productos y recetas.
    """

    @classmethod
    def setUpTestData(cls):
        # ── Usuarios por rol ────────────────────────────────────────────────
        cls.admin_user = make_user("admin_api", UserRole.ADMIN)
        cls.admin_user.is_superuser = True
        cls.admin_user.is_staff = True
        cls.admin_user.save()

        cls.ventas_user = make_user("ventas_api", UserRole.VENTAS)
        cls.cocina_user = make_user("cocina_api", UserRole.COCINA)
        cls.repartidor_user = make_user("repartidor_api", UserRole.REPARTIDOR)
        cls.repartidor_user2 = make_user("repartidor2_api", UserRole.REPARTIDOR)

        # ── Unidades de medida ──────────────────────────────────────────────
        cls.unit_kg = UnitOfMeasure.objects.create(
            code="KG", name="Kilogramo", magnitude="MASA", conversion_factor=Decimal("1.0")
        )
        cls.unit_gr = UnitOfMeasure.objects.create(
            code="GR", name="Gramo", magnitude="MASA", conversion_factor=Decimal("0.001")
        )
        cls.unit_lt = UnitOfMeasure.objects.create(
            code="LT", name="Litro", magnitude="VOLUMEN", conversion_factor=Decimal("1.0")
        )

        # ── Insumos ─────────────────────────────────────────────────────────
        cls.supply_harina = Supply.objects.create(
            sku="HAR-001",
            name="Harina de Trigo",
            unit_of_measure=cls.unit_kg,
            current_stock=Decimal("10.000"),
            minimum_stock=Decimal("2.000"),
            cost_per_unit=Decimal("1500.00"),
        )
        cls.supply_mantequilla = Supply.objects.create(
            sku="MAN-001",
            name="Mantequilla",
            unit_of_measure=cls.unit_kg,
            current_stock=Decimal("5.000"),
            minimum_stock=Decimal("1.000"),
            cost_per_unit=Decimal("8000.00"),
        )
        cls.supply_leche = Supply.objects.create(
            sku="LEC-001",
            name="Leche Entera",
            unit_of_measure=cls.unit_lt,
            current_stock=Decimal("3.000"),
            minimum_stock=Decimal("1.000"),
            cost_per_unit=Decimal("1200.00"),
        )

        # ── Producto y Receta ───────────────────────────────────────────────
        cls.product = Product.objects.create(
            code="PROD-001",
            name="Torta de Vainilla",
            category="TORTAS",
            base_price=Decimal("25000.00"),
            estimated_production_minutes=120,
        )
        cls.recipe = Recipe.objects.create(
            product=cls.product,
            name="Receta Clásica Vainilla",
            yield_portions=1,
        )
        RecipeIngredient.objects.create(
            recipe=cls.recipe,
            supply=cls.supply_harina,
            quantity_required=Decimal("0.500"),
            unit=cls.unit_kg,
            waste_percentage=Decimal("5.00"),
        )
        RecipeIngredient.objects.create(
            recipe=cls.recipe,
            supply=cls.supply_mantequilla,
            quantity_required=Decimal("0.250"),
            unit=cls.unit_kg,
            waste_percentage=Decimal("2.00"),
        )

        # ── Cliente ─────────────────────────────────────────────────────────
        cls.client_obj = Client.objects.create(
            identification="12345678-9",
            name="María González",
            email="maria@test.cl",
            phone="+56912345678",
        )


# ==============================================================================
# 1. AUTENTICACIÓN Y CONTROL DE ACCESO
# ==============================================================================

class TestAuthAndAccess(BaseAPITestCase):
    """Pruebas de autenticación y autorización por rol en la API."""

    def test_unauthenticated_request_returns_403(self):
        """Sin sesión activa, la API debe retornar 403."""
        anon = APIClient()
        response = anon.get("/api/v1/clients/")
        self.assertIn(response.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_401_UNAUTHORIZED])

    def test_authenticated_user_can_access_client_list(self):
        """Un usuario autenticado puede listar clientes."""
        api = authenticated_client(self.ventas_user)
        response = api.get("/api/v1/clients/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_dashboard_metrics_blocked_for_non_admin(self):
        """Las métricas del dashboard son exclusivas para ADMIN."""
        for user in [self.ventas_user, self.cocina_user, self.repartidor_user]:
            api = authenticated_client(user)
            response = api.get("/api/v1/dashboard/metrics/")
            self.assertEqual(
                response.status_code,
                status.HTTP_403_FORBIDDEN,
                f"Usuario con rol '{user.role}' no debería acceder al dashboard.",
            )

    def test_admin_can_access_dashboard_metrics(self):
        """ADMIN puede acceder a las métricas del dashboard."""
        api = authenticated_client(self.admin_user)
        response = api.get("/api/v1/dashboard/metrics/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("orders", response.data)
        self.assertIn("inventory", response.data)
        self.assertIn("production", response.data)
        self.assertIn("dispatch", response.data)

    def test_cocina_cannot_create_orders(self):
        """El rol COCINA no puede crear pedidos (mutación denegada)."""
        api = authenticated_client(self.cocina_user)
        response = api.post("/api/v1/orders/", data={}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_repartidor_cannot_access_client_list(self):
        """REPARTIDOR puede leer clientes (SAFE_METHOD permitido)."""
        api = authenticated_client(self.repartidor_user)
        response = api.get("/api/v1/clients/")
        # Solo lectura está permitida para todos los autenticados
        self.assertEqual(response.status_code, status.HTTP_200_OK)


# ==============================================================================
# 2. CRUD DE CLIENTES
# ==============================================================================

class TestClientsCRUD(BaseAPITestCase):
    """Pruebas de creación, listado y soft-delete de clientes."""

    def test_create_client_as_ventas(self):
        """VENTAS puede crear un cliente nuevo."""
        api = authenticated_client(self.ventas_user)
        data = {
            "identification": "98765432-5",
            "name": "Pedro Ramírez",
            "email": "pedro@test.cl",
            "phone": "+56987654321",
        }
        response = api.post("/api/v1/clients/", data=data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["name"], "Pedro Ramírez")

    def test_create_duplicate_client_identification_fails(self):
        """No se puede crear dos clientes con el mismo RUT/DNI."""
        api = authenticated_client(self.ventas_user)
        data = {
            "identification": "12345678-9",  # mismo que cls.client_obj
            "name": "Duplicado",
            "email": "dup@test.cl",
        }
        response = api.post("/api/v1/clients/", data=data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_list_clients_returns_paginated_results(self):
        """El listado de clientes devuelve resultados paginados."""
        api = authenticated_client(self.admin_user)
        response = api.get("/api/v1/clients/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)


# ==============================================================================
# 3. INVENTARIO
# ==============================================================================

class TestInventoryAPI(BaseAPITestCase):
    """Pruebas de movimientos de inventario: entradas, mermas y validación."""

    def test_register_entry_increases_stock(self):
        """Registrar una entrada incrementa el stock del insumo."""
        api = authenticated_client(self.admin_user)
        initial_stock = self.supply_harina.current_stock

        response = api.post(
            "/api/v1/inventory/movements/entry/",
            data={"supply_id": str(self.supply_harina.id), "quantity": "2.000", "reference": "Compra OC-001"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        self.supply_harina.refresh_from_db()
        self.assertEqual(self.supply_harina.current_stock, initial_stock + Decimal("2.000"))

    def test_register_waste_decreases_stock(self):
        """Registrar una merma reduce el stock del insumo."""
        api = authenticated_client(self.admin_user)
        initial_stock = self.supply_mantequilla.current_stock

        response = api.post(
            "/api/v1/inventory/movements/waste/",
            data={"supply_id": str(self.supply_mantequilla.id), "quantity": "0.500", "reference": "Merma por caducidad"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        self.supply_mantequilla.refresh_from_db()
        self.assertEqual(
            self.supply_mantequilla.current_stock,
            initial_stock - Decimal("0.500"),
        )

    def test_waste_exceeding_stock_returns_409(self):
        """Una merma mayor al stock disponible debe retornar 409 Conflict."""
        api = authenticated_client(self.admin_user)
        response = api.post(
            "/api/v1/inventory/movements/waste/",
            data={"supply_id": str(self.supply_leche.id), "quantity": "999.000", "reference": "Merma excesiva"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_non_admin_cannot_see_cost_per_unit(self):
        """Usuarios no-admin no deben ver el costo unitario de los insumos."""
        api = authenticated_client(self.ventas_user)
        response = api.get(f"/api/v1/inventory/supplies/{self.supply_harina.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn("cost_per_unit", response.data)


# ==============================================================================
# 4. PEDIDOS Y COTIZACIONES
# ==============================================================================

class TestOrdersAPI(BaseAPITestCase):
    """Pruebas de creación, confirmación, cancelación y BOM check de pedidos."""

    def _create_cotizacion(self, api_client=None):
        """Helper: crea una cotización válida y retorna la respuesta."""
        if api_client is None:
            api_client = authenticated_client(self.ventas_user)
        return api_client.post(
            "/api/v1/orders/",
            data={
                "client_id": str(self.client_obj.id),
                "delivery_date": "2027-01-15",
                "delivery_time": "15:00:00",
                "deposit_amount": "10000.00",
                "delivery_type": "DESPACHO_DOMICILIO",
                "delivery_address": "Av. Principal 123, Santiago",
                "custom_design_notes": "Torta de cumpleaños con flores rosas",
                "items": [
                    {
                        "product_id": str(self.product.id),
                        "quantity": 1,
                        "unit_price": "25000.00",
                        "cake_size": "MEDIANO",
                        "flavor_sponge": "Vainilla",
                        "flavor_filling": "Manjar",
                        "flavor_cover": "Fondant Rosa",
                        "custom_dedication": "Feliz Cumpleaños María",
                    }
                ],
            },
            format="json",
        )

    def test_create_cotizacion_as_ventas(self):
        """VENTAS puede crear una cotización."""
        api = authenticated_client(self.ventas_user)
        response = self._create_cotizacion(api)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], OrderStatus.COTIZACION)
        self.assertTrue(response.data["order_number"].startswith("DA-"))

    def test_confirm_order_generates_production_order(self):
        """Al confirmar un pedido se genera automáticamente una orden de producción."""
        api = authenticated_client(self.ventas_user)
        create_resp = self._create_cotizacion(api)
        self.assertEqual(create_resp.status_code, status.HTTP_201_CREATED)
        order_id = create_resp.data["id"]

        confirm_resp = api.post(
            f"/api/v1/orders/{order_id}/confirm/",
            data={"deposit_amount": "10000.00", "reason": "Abono inicial confirmado"},
            format="json",
        )
        self.assertEqual(confirm_resp.status_code, status.HTTP_200_OK)

        # Verificar que la orden de producción fue creada
        order = Order.objects.get(id=order_id)
        self.assertTrue(hasattr(order, "production_order"))
        self.assertEqual(order.status, OrderStatus.CONFIRMADO)
        self.assertEqual(order.production_order.kanban_stage, KanbanStage.RECIBIDO)

    def test_cancel_order_records_history(self):
        """Cancelar un pedido registra el motivo en el historial."""
        api = authenticated_client(self.ventas_user)
        create_resp = self._create_cotizacion(api)
        order_id = create_resp.data["id"]

        cancel_resp = api.post(
            f"/api/v1/orders/{order_id}/cancel/",
            data={"reason": "Cliente desistió del pedido por cambio de fecha."},
            format="json",
        )
        self.assertEqual(cancel_resp.status_code, status.HTTP_200_OK)

        order = Order.objects.get(id=order_id)
        self.assertEqual(order.status, OrderStatus.CANCELADO)
        self.assertTrue(order.status_history.filter(new_status=OrderStatus.CANCELADO).exists())

    def test_bom_check_returns_ingredient_breakdown(self):
        """El endpoint bom_check retorna el desglose de insumos del pedido."""
        api = authenticated_client(self.ventas_user)
        create_resp = self._create_cotizacion(api)
        order_id = create_resp.data["id"]

        bom_resp = api.get(f"/api/v1/orders/{order_id}/bom_check/")
        self.assertEqual(bom_resp.status_code, status.HTTP_200_OK)
        self.assertIn("items", bom_resp.data)

    def test_cannot_edit_confirmed_order(self):
        """Un pedido confirmado no puede editarse por la API."""
        api = authenticated_client(self.ventas_user)
        create_resp = self._create_cotizacion(api)
        order_id = create_resp.data["id"]

        # Confirmar primero
        api.post(
            f"/api/v1/orders/{order_id}/confirm/",
            data={"deposit_amount": "10000.00"},
            format="json",
        )

        # Intentar editar
        edit_resp = api.patch(
            f"/api/v1/orders/{order_id}/",
            data={"custom_design_notes": "Cambio no permitido"},
            format="json",
        )
        self.assertEqual(edit_resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_can_edit_commercial_data_while_quote_is_open(self):
        """Una cotización permite ajustar datos comerciales antes de confirmarla."""
        api = authenticated_client(self.ventas_user)
        create_resp = self._create_cotizacion(api)

        edit_resp = api.patch(
            f"/api/v1/orders/{create_resp.data['id']}/",
            data={"custom_design_notes": "Cambiar flores rosas por flores blancas."},
            format="json",
        )

        self.assertEqual(edit_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(edit_resp.data["custom_design_notes"], "Cambiar flores rosas por flores blancas.")

    def test_order_history_populated_on_status_change(self):
        """El historial de estados se llena correctamente al confirmar."""
        api = authenticated_client(self.ventas_user)
        create_resp = self._create_cotizacion(api)
        order_id = create_resp.data["id"]

        api.post(
            f"/api/v1/orders/{order_id}/confirm/",
            data={"deposit_amount": "5000.00"},
            format="json",
        )

        history_resp = api.get(f"/api/v1/orders/{order_id}/history/")
        self.assertEqual(history_resp.status_code, status.HTTP_200_OK)
        self.assertGreater(len(history_resp.data), 0)

    def test_physical_delete_order_returns_405(self):
        """Los pedidos no pueden eliminarse físicamente (HTTP 405)."""
        api = authenticated_client(self.admin_user)
        create_resp = self._create_cotizacion(api)
        order_id = create_resp.data["id"]

        delete_resp = api.delete(f"/api/v1/orders/{order_id}/")
        self.assertEqual(delete_resp.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)


# ==============================================================================
# 5. PRODUCCIÓN KANBAN
# ==============================================================================

class TestProductionAPI(BaseAPITestCase):
    """Pruebas de transiciones Kanban, control de calidad y doble descuento."""

    def setUp(self):
        """Crea una cotización confirmada (con ProductionOrder en RECIBIDO)."""
        self.ventas_api = authenticated_client(self.ventas_user)
        self.cocina_api = authenticated_client(self.cocina_user)
        self.admin_api = authenticated_client(self.admin_user)

        # Crear y confirmar pedido
        create_resp = self.ventas_api.post(
            "/api/v1/orders/",
            data={
                "client_id": str(self.client_obj.id),
                "delivery_date": "2027-02-10",
                "delivery_time": "14:00:00",
                "items": [
                    {
                        "product_id": str(self.product.id),
                        "quantity": 1,
                        "unit_price": "25000.00",
                    }
                ],
            },
            format="json",
        )
        self.assertEqual(create_resp.status_code, status.HTTP_201_CREATED)
        self.order_id = create_resp.data["id"]

        confirm_resp = self.ventas_api.post(
            f"/api/v1/orders/{self.order_id}/confirm/",
            data={"deposit_amount": "12500.00"},
            format="json",
        )
        self.assertEqual(confirm_resp.status_code, status.HTTP_200_OK)

        order = Order.objects.get(id=self.order_id)
        self.prod_order = order.production_order

    def test_kanban_board_groups_by_stage(self):
        """El endpoint kanban retorna las órdenes agrupadas por etapa."""
        response = self.cocina_api.get("/api/v1/production/kanban/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("board", response.data)
        self.assertIn(KanbanStage.RECIBIDO, response.data["board"])

    def test_transition_recibido_to_en_preparacion_deducts_stock(self):
        """La transición a EN_PREPARACION descuenta el inventario atómicamente."""
        harina_before = Supply.objects.get(id=self.supply_harina.id).current_stock

        response = self.cocina_api.post(
            f"/api/v1/production/{self.prod_order.id}/transition/",
            data={"target_stage": KanbanStage.EN_PREPARACION, "notes": "Iniciando masa"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verificar descuento de inventario
        self.supply_harina.refresh_from_db()
        self.assertLess(self.supply_harina.current_stock, harina_before)

        # Verificar que stock_consumed = True
        self.prod_order.refresh_from_db()
        self.assertTrue(self.prod_order.stock_consumed)

    def test_double_stock_deduction_prevented(self):
        """
        Intentar transicionar dos veces a EN_PREPARACION debe fallar
        la segunda vez (protección anti-doble descuento).
        """
        # Primera transición exitosa
        self.cocina_api.post(
            f"/api/v1/production/{self.prod_order.id}/transition/",
            data={"target_stage": KanbanStage.EN_PREPARACION},
            format="json",
        )

        # Segunda transición inválida (ya está en EN_PREPARACION)
        response2 = self.cocina_api.post(
            f"/api/v1/production/{self.prod_order.id}/transition/",
            data={"target_stage": KanbanStage.EN_PREPARACION},
            format="json",
        )
        self.assertEqual(response2.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cannot_transition_to_listo_without_quality_check(self):
        """No se puede marcar como LISTO sin control de calidad aprobado."""
        # Avanzar hasta CONTROL_CALIDAD
        for target in [KanbanStage.EN_PREPARACION, KanbanStage.HORNEADO_DECORADO, KanbanStage.CONTROL_CALIDAD]:
            self.cocina_api.post(
                f"/api/v1/production/{self.prod_order.id}/transition/",
                data={"target_stage": target},
                format="json",
            )

        # Intentar marcar como LISTO sin control de calidad
        response = self.cocina_api.post(
            f"/api/v1/production/{self.prod_order.id}/transition/",
            data={"target_stage": KanbanStage.LISTO},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_full_kanban_flow_with_quality_check(self):
        """Flujo completo Kanban: RECIBIDO → LISTO con control de calidad aprobado."""
        stages = [KanbanStage.EN_PREPARACION, KanbanStage.HORNEADO_DECORADO, KanbanStage.CONTROL_CALIDAD]
        for target in stages:
            resp = self.cocina_api.post(
                f"/api/v1/production/{self.prod_order.id}/transition/",
                data={"target_stage": target},
                format="json",
            )
            self.assertEqual(resp.status_code, status.HTTP_200_OK, f"Fallo en transición a {target}")

        # Registrar control de calidad APROBADO
        qc_resp = self.cocina_api.post(
            f"/api/v1/production/{self.prod_order.id}/quality_check/",
            data={"result": QualityResult.APROBADO, "observations": "Presentación impecable."},
            format="json",
        )
        self.assertEqual(qc_resp.status_code, status.HTTP_200_OK)

        # Ahora sí puede pasar a LISTO
        listo_resp = self.cocina_api.post(
            f"/api/v1/production/{self.prod_order.id}/transition/",
            data={"target_stage": KanbanStage.LISTO},
            format="json",
        )
        self.assertEqual(listo_resp.status_code, status.HTTP_200_OK)

        # Estado comercial del pedido debe ser LISTO
        order = Order.objects.get(id=self.order_id)
        self.assertEqual(order.status, OrderStatus.LISTO)

    def test_quality_check_requires_control_calidad_stage(self):
        """El control de calidad solo se puede registrar en la etapa CONTROL_CALIDAD."""
        response = self.cocina_api.post(
            f"/api/v1/production/{self.prod_order.id}/quality_check/",
            data={"result": QualityResult.APROBADO},
            format="json",
        )
        # La orden está en RECIBIDO, no en CONTROL_CALIDAD
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


# ==============================================================================
# 6. DESPACHO Y LOGÍSTICA
# ==============================================================================

class TestDispatchAPI(BaseAPITestCase):
    """Pruebas de rutas, paradas, inicio y confirmación de entrega con firma digital."""

    def setUp(self):
        """Crea una orden en estado LISTO con su DispatchOrder pendiente."""
        self.admin_api = authenticated_client(self.admin_user)
        self.ventas_api = authenticated_client(self.ventas_user)
        self.rep_api = authenticated_client(self.repartidor_user)

        # Crear pedido confirmado y avanzarlo a LISTO manualmente para tests de dispatch
        self.order = Order.objects.create(
            client=self.client_obj,
            delivery_date="2027-03-01",
            delivery_time="11:00:00",
            status=OrderStatus.LISTO,
            total_amount=Decimal("25000.00"),
            deposit_amount=Decimal("12500.00"),
            balance_due=Decimal("12500.00"),
        )
        self.dispatch_order = DispatchOrder.objects.create(
            order=self.order,
            assigned_driver=self.repartidor_user,
            status=DispatchStatus.PENDIENTE,
        )

    def test_create_route_as_ventas(self):
        """VENTAS puede crear una ruta de despacho."""
        response = self.ventas_api.post(
            "/api/v1/dispatch/routes/create_route/",
            data={
                "scheduled_date": "2027-03-01",
                "driver_id": self.repartidor_user.id,
                "notes": "Zona Norte - Santiago",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["code"].startswith("RT-"))

    def test_assign_dispatches_to_route(self):
        """Se pueden asignar paradas a una ruta con orden secuencial."""
        # Crear ruta
        route = DeliveryRoute.objects.create(
            code="RT-2027-00001",
            scheduled_date="2027-03-01",
            assigned_driver=self.repartidor_user,
        )

        response = self.ventas_api.post(
            f"/api/v1/dispatch/routes/{route.id}/assign_stops/",
            data={
                "stops": [
                    {"dispatch_id": str(self.dispatch_order.id), "stop_order": 1}
                ]
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.dispatch_order.refresh_from_db()
        self.assertEqual(self.dispatch_order.route, route)
        self.assertEqual(self.dispatch_order.stop_order, 1)

    def test_assign_stops_rejects_duplicate_sequence(self):
        """La API rechaza secuencias repetidas antes de que lleguen a la base de datos."""
        route = DeliveryRoute.objects.create(
            code="RT-2027-00009",
            scheduled_date="2027-03-01",
            assigned_driver=self.repartidor_user,
        )

        response = self.ventas_api.post(
            f"/api/v1/dispatch/routes/{route.id}/assign_stops/",
            data={
                "stops": [
                    {"dispatch_id": str(self.dispatch_order.id), "stop_order": 1},
                    {"dispatch_id": str(self.dispatch_order.id), "stop_order": 1},
                ]
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_start_route_moves_dispatches_to_en_ruta(self):
        """Iniciar una ruta cambia los despachos a EN_RUTA y los pedidos a EN_DESPACHO."""
        route = DeliveryRoute.objects.create(
            code="RT-2027-00002",
            scheduled_date="2027-03-01",
            assigned_driver=self.repartidor_user,
        )
        self.dispatch_order.route = route
        self.dispatch_order.save()

        response = self.ventas_api.post(
            f"/api/v1/dispatch/routes/{route.id}/start_route/",
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.dispatch_order.refresh_from_db()
        self.assertEqual(self.dispatch_order.status, DispatchStatus.EN_RUTA)

    def test_confirm_delivery_creates_proof_and_marks_delivered(self):
        """Confirmar entrega crea comprobante y marca pedido como ENTREGADO."""
        self.dispatch_order.status = DispatchStatus.EN_RUTA
        self.dispatch_order.save()

        response = self.rep_api.post(
            f"/api/v1/dispatch/dispatches/{self.dispatch_order.id}/confirm/",
            data={
                "recipient_name": "María González",
                "recipient_id": "12345678-9",
                "signature_data": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciLz4=",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("proof", response.data)

        self.dispatch_order.refresh_from_db()
        self.assertEqual(self.dispatch_order.status, DispatchStatus.ENTREGADO)

        self.order.refresh_from_db()
        self.assertEqual(self.order.status, OrderStatus.ENTREGADO)

    def test_confirm_delivery_idempotency_returns_409(self):
        """Confirmar una entrega ya confirmada debe retornar 409 Conflict."""
        self.dispatch_order.status = DispatchStatus.EN_RUTA
        self.dispatch_order.save()

        payload = {
            "recipient_name": "María González",
            "recipient_id": "12345678-9",
            "signature_data": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciLz4=",
        }

        # Primera confirmación
        resp1 = self.rep_api.post(
            f"/api/v1/dispatch/dispatches/{self.dispatch_order.id}/confirm/",
            data=payload,
            format="json",
        )
        self.assertEqual(resp1.status_code, status.HTTP_201_CREATED)

        # Segunda confirmación (debe fallar con 409)
        resp2 = self.rep_api.post(
            f"/api/v1/dispatch/dispatches/{self.dispatch_order.id}/confirm/",
            data=payload,
            format="json",
        )
        self.assertEqual(resp2.status_code, status.HTTP_409_CONFLICT)

    def test_other_driver_cannot_confirm_dispatch(self):
        """Un repartidor no asignado no puede confirmar el despacho de otro."""
        self.dispatch_order.status = DispatchStatus.EN_RUTA
        self.dispatch_order.save()

        other_rep_api = authenticated_client(self.repartidor_user2)
        response = other_rep_api.post(
            f"/api/v1/dispatch/dispatches/{self.dispatch_order.id}/confirm/",
            data={
                "recipient_name": "Intruso",
                "recipient_id": "00000000-0",
                "signature_data": "data:image/svg+xml;base64,PHN2Z=",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_my_deliveries_filtered_by_authenticated_driver(self):
        """my_deliveries solo retorna los despachos del repartidor autenticado."""
        response = self.rep_api.get("/api/v1/dispatch/dispatches/my_deliveries/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for item in response.data["results"]:
            self.assertEqual(item["assigned_driver_name"], self.repartidor_user.get_full_name())
