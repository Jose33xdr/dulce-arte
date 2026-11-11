"""
Modelos de rutas de despacho, paradas ordenadas y comprobantes con firma digital para Dulce Arte.
Permite certificar la recepción inmutable de pedidos personalizados.
"""

from django.conf import settings
from django.db import models
from django.db.models import Q
from apps.core.models import TimeStampedModel
from apps.orders.models import Order


class RouteStatus(models.TextChoices):
    PROGRAMADA = "PROGRAMADA", "Programada"
    EN_CURSO = "EN_CURSO", "En Curso / En Ruta"
    COMPLETADA = "COMPLETADA", "Completada"
    CANCELADA = "CANCELADA", "Cancelada"


class DeliveryRoute(TimeStampedModel):
    """
    Ruta logística planificada que agrupa múltiples paradas de despacho para un repartidor.
    """

    code = models.CharField(
        max_length=30,
        unique=True,
        db_index=True,
        verbose_name="Código de Ruta (RT-YYYY-XXXXX)",
    )
    assigned_driver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="delivery_routes",
        verbose_name="Repartidor asignado",
    )
    scheduled_date = models.DateField(
        db_index=True,
        verbose_name="Fecha programada de ruta",
    )
    status = models.CharField(
        max_length=25,
        choices=RouteStatus.choices,
        default=RouteStatus.PROGRAMADA,
        verbose_name="Estado de la ruta",
    )
    notes = models.TextField(
        blank=True,
        verbose_name="Observaciones de ruta",
        help_text="Zona geográfica, restricciones de tráfico o instrucciones para el repartidor.",
    )

    class Meta:
        verbose_name = "Ruta de Despacho"
        verbose_name_plural = "Rutas de Despacho"
        ordering = ["-scheduled_date", "code"]
        indexes = [
            models.Index(fields=["code"], name="idx_route_code"),
            models.Index(fields=["scheduled_date"], name="idx_route_date"),
        ]

    def __str__(self):
        driver_str = self.assigned_driver.get_full_name() if self.assigned_driver else "Sin asignar"
        return f"{self.code} - {self.scheduled_date} ({driver_str})"


class DispatchStatus(models.TextChoices):
    PENDIENTE = "PENDIENTE", "Pendiente de Asignación / Salida"
    EN_RUTA = "EN_RUTA", "En Ruta con Repartidor"
    ENTREGADO = "ENTREGADO", "Entregado conforme"
    FALLIDO = "FALLIDO", "Intento Fallido (Cliente ausente)"


class DispatchOrder(TimeStampedModel):
    """
    Despacho individual asociado a un pedido con parada ordenada en la ruta.
    """

    order = models.OneToOneField(
        Order,
        on_delete=models.PROTECT,
        related_name="dispatch_order",
        verbose_name="Pedido a despachar",
    )
    route = models.ForeignKey(
        DeliveryRoute,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="dispatches",
        verbose_name="Ruta asignada",
    )
    stop_order = models.PositiveIntegerField(
        default=1,
        verbose_name="Orden de parada en la ruta",
        help_text="Secuencia de entrega en el recorrido (1, 2, 3...).",
    )
    assigned_driver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_dispatches",
        verbose_name="Repartidor responsable",
    )
    status = models.CharField(
        max_length=25,
        choices=DispatchStatus.choices,
        default=DispatchStatus.PENDIENTE,
        db_index=True,
        verbose_name="Estado del despacho",
    )
    dispatched_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Fecha y hora de salida",
    )
    delivered_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Fecha y hora de entrega final",
    )

    class Meta:
        verbose_name = "Despacho de Pedido"
        verbose_name_plural = "Despachos de Pedidos"
        ordering = ["route", "stop_order", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["route", "stop_order"],
                condition=Q(route__isnull=False),
                name="unique_route_stop_order",
            ),
        ]
        indexes = [
            models.Index(fields=["status"], name="idx_dispatch_status"),
        ]

    def __str__(self):
        return f"Despacho {self.order.order_number} ({self.get_status_display()})"


class DeliveryProof(TimeStampedModel):
    """
    Comprobante legal y digital de entrega.
    Almacena firma digital en SVG/Base64, receptor y fotografía de respaldo.
    """

    dispatch_order = models.OneToOneField(
        DispatchOrder,
        on_delete=models.PROTECT,
        related_name="proof",
        verbose_name="Despacho certificado",
    )
    recipient_name = models.CharField(
        max_length=150,
        verbose_name="Nombre de quien recibe",
    )
    recipient_id = models.CharField(
        max_length=25,
        verbose_name="RUT / DNI del receptor",
    )
    signature_data = models.TextField(
        verbose_name="Firma digital (DataURI SVG / Base64)",
        help_text="Trazo capturado en el canvas digital del dispositivo.",
    )
    proof_photo = models.ImageField(
        upload_to="dispatches/proofs/%Y/%m/",
        null=True,
        blank=True,
        verbose_name="Fotografía comprobante",
        help_text="Foto opcional del pastel entregado o domicilio.",
    )
    registered_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha y hora de certificación",
    )

    class Meta:
        verbose_name = "Comprobante de Entrega"
        verbose_name_plural = "Comprobantes de Entrega"
        ordering = ["-registered_at"]

    def __str__(self):
        return f"Certificado {self.dispatch_order.order.order_number} - Recibe: {self.recipient_name}"
