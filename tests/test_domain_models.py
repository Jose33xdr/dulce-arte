"""
Suite de pruebas automatizadas para la Fase 3 de Dulce Arte:
Modelado Relacional, Integridad de Datos, Restricciones y Django Admin.
"""

from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import IntegrityError, models
from django.test import TestCase, Client
from django.utils import timezone

from apps.users.models import User, UserRole
from apps.clients.models import Client as BakeryClient
from apps.inventory.models import MagnitudeType, MovementType, StockMovement, Supply, UnitOfMeasure
from apps.recipes.models import Product, ProductCategory, Recipe, RecipeIngredient
from apps.orders.models import DeliveryType, Order, OrderItem, OrderStatus, OrderStatusHistory
from apps.production.models import KanbanStage, ProductionOrder, QualityCheck, QualityResult
from apps.dispatch.models import DeliveryProof, DeliveryRoute, DispatchOrder, DispatchStatus, RouteStatus


class DomainModelsIntegrityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        # 1. Unidades de Medida Estándar
        cls.u_kg = UnitOfMeasure.objects.create(
            code="KG", name="Kilogramo", magnitude=MagnitudeType.MASA, conversion_factor=Decimal("1.000000")
        )
        cls.u_gr = UnitOfMeasure.objects.create(
            code="GR", name="Gramo", magnitude=MagnitudeType.MASA, conversion_factor=Decimal("0.001000")
        )
        cls.u_lt = UnitOfMeasure.objects.create(
            code="LT", name="Litro", magnitude=MagnitudeType.VOLUMEN, conversion_factor=Decimal("1.000000")
        )
        cls.u_ml = UnitOfMeasure.objects.create(
            code="ML", name="Mililitro", magnitude=MagnitudeType.VOLUMEN, conversion_factor=Decimal("0.001000")
        )
        cls.u_un = UnitOfMeasure.objects.create(
            code="UNIDAD", name="Unidad", magnitude=MagnitudeType.UNIDAD, conversion_factor=Decimal("1.000000")
        )

        # 2. Insumos Base
        cls.harina = Supply.objects.create(
            sku="INS-HAR-001",
            name="Harina de Trigo Especial",
            unit_of_measure=cls.u_kg,
            current_stock=Decimal("50.000"),
            minimum_stock=Decimal("10.000"),
            cost_per_unit=Decimal("1200.00"),
        )
        cls.leche = Supply.objects.create(
            sku="INS-LEC-001",
            name="Leche Entera",
            unit_of_measure=cls.u_lt,
            current_stock=Decimal("30.000"),
            minimum_stock=Decimal("5.000"),
            cost_per_unit=Decimal("950.00"),
        )

        # 3. Usuarios Operativos
        cls.admin_user = User.objects.create_superuser(
            username="admin_domain",
            email="admin@dulcearte.cl",
            password="AdminPassword123!",
            role=UserRole.ADMIN,
        )
        cls.cook_user = User.objects.create_user(
            username="chef_pastry",
            email="chef@dulcearte.cl",
            password="ChefPassword123!",
            role=UserRole.COCINA,
        )
        cls.driver_user = User.objects.create_user(
            username="driver_juan",
            email="driver@dulcearte.cl",
            password="DriverPassword123!",
            role=UserRole.REPARTIDOR,
        )

        # 4. Cliente Base
        cls.client_obj = BakeryClient.objects.create(
            identification="15.234.567-2",
            name="Carolina Silva Tapia",
            email="carolina@example.com",
            phone="+56912345678",
            address="Av. Providencia 1234, Depto 502",
        )

        # 5. Producto Base
        cls.torta_chocolate = Product.objects.create(
            code="PRD-TOR-001",
            name="Torta Suprema de Chocolate Belga",
            category=ProductCategory.TORTA_TRADICIONAL,
            base_price=Decimal("32000.00"),
            estimated_production_minutes=90,
        )

    def test_client_creation_and_normalization(self):
        """Verifica la creación y formateo estándar del RUT del cliente."""
        client = BakeryClient.objects.get(id=self.client_obj.id)
        self.assertEqual(client.name, "Carolina Silva Tapia")
        self.assertTrue(client.is_active)
        self.assertIn("15234567-2", client.identification.replace(".", ""))

    def test_client_duplicate_identification_fails(self):
        """Verifica que no se permita registrar dos clientes con la misma identificación."""
        with self.assertRaises(IntegrityError):
            BakeryClient.objects.create(
                identification=self.client_obj.identification,
                name="Otro Cliente Duplicado",
            )

    def test_negative_stock_constraint(self):
        """Verifica que la base de datos rechace saldo negativo de insumos por CheckConstraint."""
        with self.assertRaises(IntegrityError):
            Supply.objects.create(
                sku="INS-ERR-001",
                name="Insumo Negativo",
                unit_of_measure=self.u_kg,
                current_stock=Decimal("-5.000"),  # Violación chk_supply_stock_no_negativo
            )

    def test_incompatible_units_validation(self):
        """Verifica que una receta rechace ingredientes con magnitud incompatible (ej. volumen para harina)."""
        recipe = Recipe.objects.create(
            product=self.torta_chocolate,
            name="Receta Torta Suprema Chocolate",
            yield_portions=15,
        )
        # Intentar añadir Harina (masa) usando Litros (volumen)
        ingredient = RecipeIngredient(
            recipe=recipe,
            supply=self.harina,
            quantity_required=Decimal("2.000"),
            unit=self.u_lt,  # Incompatible con KG de la harina
        )
        with self.assertRaises(ValidationError) as ctx:
            ingredient.full_clean()
        self.assertIn("Incompatibilidad de magnitud", str(ctx.exception))

    def test_invalid_quantity_constraint(self):
        """Verifica que no se permitan cantidades cero o negativas en ingredientes y movimientos."""
        recipe = Recipe.objects.create(
            product=self.torta_chocolate,
            name="Receta Base Inv",
            yield_portions=10,
        )
        with self.assertRaises(IntegrityError):
            RecipeIngredient.objects.create(
                recipe=recipe,
                supply=self.harina,
                quantity_required=Decimal("0.000"),  # Violación chk_ingredient_cantidad_positiva
                unit=self.u_kg,
            )

    def test_recipe_ingredient_conversion_and_waste(self):
        """Verifica el cálculo de cantidad efectiva con factor de merma y conversión a unidad base."""
        recipe = Recipe.objects.create(
            product=self.torta_chocolate,
            name="Receta Torta Chocolate con Merma",
            yield_portions=12,
        )
        # 500 gramos de harina con 10% de merma = 550 gr = 0.550 kg
        ingredient = RecipeIngredient.objects.create(
            recipe=recipe,
            supply=self.harina,
            quantity_required=Decimal("500.000"),
            unit=self.u_gr,
            waste_percentage=Decimal("10.00"),
        )
        effective_qty = ingredient.get_effective_quantity()
        base_unit_qty = ingredient.get_base_unit_quantity()

        self.assertEqual(effective_qty, Decimal("550.00000"))
        self.assertAlmostEqual(base_unit_qty, Decimal("0.550"), places=3)

    def test_order_creation_with_multiple_items_and_balance(self):
        """Verifica pedido con ítems personalizados y cálculo de saldo pendiente."""
        galletas = Product.objects.create(
            code="PRD-GAL-001",
            name="Caja Galletas Finas Artesanales",
            category=ProductCategory.REPOSTERIA_INDIVIDUAL,
            base_price=Decimal("8000.00"),
        )

        order = Order.objects.create(
            order_number="DA-2026-00001",
            client=self.client_obj,
            status=OrderStatus.CONFIRMADO,
            delivery_date=timezone.now().date(),
            delivery_time=timezone.now().time(),
            delivery_type=DeliveryType.DESPACHO_DOMICILIO,
            delivery_address="Av. Providencia 1234, Depto 502",
            total_amount=Decimal("40000.00"),
            deposit_amount=Decimal("20000.00"),
            balance_due=Decimal("20000.00"),
            custom_design_notes="Decoración con rosas en fondant burdeos y detalles dorados",
        )

        # Ítem 1: Torta personalizada
        item1 = OrderItem.objects.create(
            order=order,
            product=self.torta_chocolate,
            quantity=1,
            unit_price=Decimal("32000.00"),
            subtotal=Decimal("32000.00"),
            cake_size="20 porciones",
            flavor_sponge="Chocolate Belga",
            flavor_filling="Ganache de frambuesa y manjar",
            flavor_cover="Fondant satinado blanco y burdeos",
            custom_dedication="¡Feliz Aniversario!",
        )

        # Ítem 2: Galletas
        item2 = OrderItem.objects.create(
            order=order,
            product=galletas,
            quantity=1,
            unit_price=Decimal("8000.00"),
            subtotal=Decimal("8000.00"),
        )

        self.assertEqual(order.items.count(), 2)
        self.assertEqual(order.balance_due, Decimal("20000.00"))
        self.assertEqual(item1.subtotal + item2.subtotal, order.total_amount)

    def test_order_deposit_cannot_exceed_total(self):
        """Verifica que el abono no pueda superar el monto total del pedido."""
        order = Order(
            order_number="DA-2026-00099",
            client=self.client_obj,
            delivery_date=timezone.now().date(),
            delivery_time=timezone.now().time(),
            total_amount=Decimal("15000.00"),
            deposit_amount=Decimal("20000.00"),  # Inválido
        )
        with self.assertRaises(ValidationError):
            order.clean()

    def test_protected_deletion_restrictions(self):
        """Verifica que registros históricos no puedan eliminarse físicamente (PROTECT)."""
        order = Order.objects.create(
            order_number="DA-2026-00002",
            client=self.client_obj,
            delivery_date=timezone.now().date(),
            delivery_time=timezone.now().time(),
            total_amount=Decimal("10000.00"),
        )
        # Intentar borrar el cliente con pedidos asociados debe fallar por ProtectedError
        with self.assertRaises(models.ProtectedError):
            self.client_obj.delete()

    def test_production_order_and_quality_check(self):
        """Verifica la vinculación entre pedido, orden de producción y control de calidad."""
        order = Order.objects.create(
            order_number="DA-2026-00003",
            client=self.client_obj,
            status=OrderStatus.EN_PRODUCCION,
            delivery_date=timezone.now().date(),
            delivery_time=timezone.now().time(),
            total_amount=Decimal("25000.00"),
        )

        prod_order = ProductionOrder.objects.create(
            order=order,
            production_code="OP-2026-00001",
            kanban_stage=KanbanStage.EN_PREPARACION,
            assigned_cook=self.cook_user,
            stock_consumed=False,
        )

        self.assertFalse(prod_order.stock_consumed)
        self.assertEqual(prod_order.order, order)

        # Control de calidad
        qc = QualityCheck.objects.create(
            production_order=prod_order,
            inspected_by=self.admin_user,
            result=QualityResult.APROBADO,
            observations="Presentación impecable, peso y textura conforme.",
        )
        self.assertEqual(prod_order.quality_check, qc)

    def test_delivery_route_and_dispatch_with_proof(self):
        """Verifica ruta de despacho con paradas ordenadas y comprobante de entrega digital."""
        order = Order.objects.create(
            order_number="DA-2026-00004",
            client=self.client_obj,
            status=OrderStatus.EN_DESPACHO,
            delivery_date=timezone.now().date(),
            delivery_time=timezone.now().time(),
            delivery_type=DeliveryType.DESPACHO_DOMICILIO,
            delivery_address="Calle Las Rosas 442, Las Condes",
            total_amount=Decimal("35000.00"),
        )

        route = DeliveryRoute.objects.create(
            code="RT-2026-00001",
            assigned_driver=self.driver_user,
            scheduled_date=timezone.now().date(),
            status=RouteStatus.EN_CURSO,
        )

        dispatch = DispatchOrder.objects.create(
            order=order,
            route=route,
            stop_order=1,
            assigned_driver=self.driver_user,
            status=DispatchStatus.EN_RUTA,
        )

        self.assertEqual(route.dispatches.count(), 1)

        # Registrar comprobante con firma digital
        proof = DeliveryProof.objects.create(
            dispatch_order=dispatch,
            recipient_name="Marcela Gómez",
            recipient_id="12.987.654-3",
            signature_data="data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciPjwvc3ZnPg==",
        )

        self.assertEqual(dispatch.proof, proof)
        self.assertEqual(proof.recipient_name, "Marcela Gómez")

    def test_admin_site_accessibility(self):
        """Verifica que el panel administrativo cargue con los modelos registrados para el admin."""
        client = Client()
        client.force_login(self.admin_user)

        response = client.get("/admin/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Dulce Arte — Administración")
        # Verificar presencia de secciones clave
        self.assertContains(response, "Clientes")
        self.assertContains(response, "Insumos")
        self.assertContains(response, "Recetas (BOM)")
        self.assertContains(response, "Pedidos")
        self.assertContains(response, "Órdenes de Producción")
        self.assertContains(response, "Rutas de Despacho")
