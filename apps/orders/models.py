"""
Modelos de pedidos, cotizaciones, personalizaciones e historial de estados para Dulce Arte.
Permite registrar especificaciones de diseño, sabores y control financiero estricto.
"""

from decimal import Decimal
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q
from apps.core.models import TimeStampedModel
from apps.clients.models import Client
from apps.recipes.models import Product


class OrderStatus(models.TextChoices):
    COTIZACION = "COTIZACION", "Cotización"
    CONFIRMADO = "CONFIRMADO", "Confirmado (Abonado)"
    EN_PRODUCCION = "EN_PRODUCCION", "En Producción (Cocina)"
    LISTO = "LISTO", "Listo para Entrega"
    EN_DESPACHO = "EN_DESPACHO", "En Despacho / Ruta"
    ENTREGADO = "ENTREGADO", "Entregado conforme"
    CANCELADO = "CANCELADO", "Cancelado"


class DeliveryType(models.TextChoices):
    RETIRO_TIENDA = "RETIRO_TIENDA", "Retiro en Pastelería"
    DESPACHO_DOMICILIO = "DESPACHO_DOMICILIO", "Despacho a Domicilio"


class Order(TimeStampedModel):
    """
    Pedido comercial o cotización de pastelería personalizada.
    """

    order_number = models.CharField(
        max_length=25,
        unique=True,
        db_index=True,
        verbose_name="N° Pedido (DA-YYYY-XXXXX)",
        help_text="Identificador único correlativo del pedido.",
    )
    client = models.ForeignKey(
        Client,
        on_delete=models.PROTECT,
        related_name="orders",
        verbose_name="Cliente",
    )
    status = models.CharField(
        max_length=25,
        choices=OrderStatus.choices,
        default=OrderStatus.COTIZACION,
        db_index=True,
        verbose_name="Estado comercial",
    )
    delivery_date = models.DateField(
        db_index=True,
        verbose_name="Fecha de entrega programada",
    )
    delivery_time = models.TimeField(
        verbose_name="Hora de entrega programada",
    )
    delivery_type = models.CharField(
        max_length=25,
        choices=DeliveryType.choices,
        default=DeliveryType.RETIRO_TIENDA,
        verbose_name="Tipo de entrega",
    )
    delivery_address = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Dirección de entrega",
        help_text="Requerida si el tipo de entrega es a domicilio.",
    )
    total_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Monto Total ($)",
    )
    deposit_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Abono ($)",
        help_text="Monto anticipado pagado por el cliente.",
    )
    balance_due = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Saldo Pendiente ($)",
    )
    custom_design_notes = models.TextField(
        blank=True,
        verbose_name="Observaciones de diseño",
        help_text="Detalles estéticos, colores de fondant, estilo decorativo.",
    )
    reference_image = models.ImageField(
        upload_to="orders/reference/%Y/%m/",
        null=True,
        blank=True,
        verbose_name="Imagen de referencia de diseño",
    )

    class Meta:
        verbose_name = "Pedido"
        verbose_name_plural = "Pedidos"
        ordering = ["-delivery_date", "-delivery_time"]
        constraints = [
            models.CheckConstraint(
                condition=Q(total_amount__gte=0),
                name="chk_order_total_no_negativo",
            ),
            models.CheckConstraint(
                condition=Q(deposit_amount__gte=0),
                name="chk_order_abono_no_negativo",
            ),
            models.CheckConstraint(
                condition=Q(balance_due__gte=0),
                name="chk_order_saldo_no_negativo",
            ),
            models.CheckConstraint(
                condition=Q(deposit_amount__lte=F("total_amount")),
                name="chk_order_abono_menor_o_igual_total",
            ),
        ]
        indexes = [
            models.Index(fields=["order_number"], name="idx_order_number"),
            models.Index(fields=["status"], name="idx_order_status"),
            models.Index(fields=["delivery_date"], name="idx_order_delivery_date"),
        ]

    def clean(self):
        super().clean()
        if self.delivery_type == DeliveryType.DESPACHO_DOMICILIO and not self.delivery_address:
            # Si tiene dirección de cliente, heredarla si no se especificó otra
            if self.client and self.client.address:
                self.delivery_address = self.client.address
            else:
                raise ValidationError({"delivery_address": "Para despacho a domicilio debe especificar una dirección de entrega."})

        # Recalcular saldo pendiente
        if self.total_amount is not None and self.deposit_amount is not None:
            if self.deposit_amount > self.total_amount:
                raise ValidationError({"deposit_amount": "El monto de abono no puede superar el monto total del pedido."})
            self.balance_due = self.total_amount - self.deposit_amount

    def __str__(self):
        return f"{self.order_number} - {self.client.name} ({self.get_status_display()})"


class OrderItem(TimeStampedModel):
    """
    Ítem específico contenido en un pedido con detalle de personalización artesanal.
    """

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name="Pedido",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="order_items",
        verbose_name="Producto",
    )
    quantity = models.PositiveIntegerField(
        default=1,
        verbose_name="Cantidad",
    )
    unit_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Precio Unitario ($)",
    )
    subtotal = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Subtotal ($)",
    )

    # Atributos de personalización de pastelería artesanal
    cake_size = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Tamaño / Porciones",
        help_text="ej. 15 porciones, 30 porciones, 2 pisos.",
    )
    flavor_sponge = models.CharField(
        max_length=60,
        blank=True,
        verbose_name="Sabor de bizcocho",
        help_text="ej. Vainilla bourbon, Chocolate belga, Zanahoria nuez.",
    )
    flavor_filling = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Sabor de relleno",
        help_text="ej. Manjar artesanal con nueces, Ganache de maracuyá.",
    )
    flavor_cover = models.CharField(
        max_length=60,
        blank=True,
        verbose_name="Cobertura",
        help_text="ej. Merengue suizo, Fondant satinado, Buttercream.",
    )
    custom_dedication = models.CharField(
        max_length=150,
        blank=True,
        verbose_name="Dedicatoria personalizada",
        help_text="Texto a escribir sobre el pastel o tarjeta.",
    )
    customizations = models.TextField(
        blank=True,
        verbose_name="Detalles e ingredientes adicionales",
        help_text="Modificaciones a la receta estándar que alteran insumos o cotización.",
    )

    class Meta:
        verbose_name = "Ítem de Pedido"
        verbose_name_plural = "Ítems de Pedido"
        ordering = ["created_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(quantity__gt=0),
                name="chk_order_item_cantidad_mayor_cero",
            ),
            models.CheckConstraint(
                condition=Q(unit_price__gte=0),
                name="chk_order_item_precio_no_negativo",
            ),
            models.CheckConstraint(
                condition=Q(subtotal__gte=0),
                name="chk_order_item_subtotal_no_negativo",
            ),
        ]

    def clean(self):
        super().clean()
        if self.quantity is not None and self.unit_price is not None:
            self.subtotal = Decimal(self.quantity) * self.unit_price

    def __str__(self):
        return f"{self.quantity}x {self.product.name} (${self.subtotal})"


class OrderStatusHistory(TimeStampedModel):
    """
    Bitácora inmutable de cambios de estado del pedido para trazabilidad comercial.
    """

    order = models.ForeignKey(
        Order,
        on_delete=models.PROTECT,
        related_name="status_history",
        verbose_name="Pedido",
    )
    previous_status = models.CharField(
        max_length=25,
        verbose_name="Estado anterior",
    )
    new_status = models.CharField(
        max_length=25,
        verbose_name="Estado nuevo",
    )
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        verbose_name="Usuario responsable",
    )
    reason = models.TextField(
        blank=True,
        verbose_name="Motivo / Observación del cambio",
    )

    class Meta:
        verbose_name = "Historial de Estado de Pedido"
        verbose_name_plural = "Historiales de Estado de Pedido"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["created_at"], name="idx_history_created"),
        ]

    def __str__(self):
        return f"{self.order.order_number}: {self.previous_status} -> {self.new_status} ({self.created_at.strftime('%d/%m/%Y %H:%M')})"
