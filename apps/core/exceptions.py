"""
Excepciones de dominio personalizadas para reglas de negocio en Dulce Arte.
Permiten desacoplar la lógica de negocio de los códigos de respuesta HTTP.
"""

from rest_framework import status
from rest_framework.exceptions import APIException


class BusinessLogicException(APIException):
    """Excepción base para violaciones de reglas de negocio."""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Ha ocurrido una violación de regla de negocio."
    default_code = "business_logic_error"


class InsufficientStockException(BusinessLogicException):
    """Lanzada cuando un insumo no tiene saldo suficiente para cubrir una receta."""
    status_code = status.HTTP_409_CONFLICT
    default_detail = "Stock insuficiente para procesar la orden."
    default_code = "insufficient_stock"


class StockAlreadyConsumedException(BusinessLogicException):
    """Lanzada para evitar descuentos duplicados de inventario."""
    status_code = status.HTTP_409_CONFLICT
    default_detail = "Los insumos de esta orden de producción ya fueron descontados previamente."
    default_code = "stock_already_consumed"


class InvalidStateTransitionException(BusinessLogicException):
    """Lanzada cuando se intenta una transición de estado no permitida."""
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_detail = "La transición de estado solicitada no es válida en el flujo actual."
    default_code = "invalid_state_transition"


class DeliveryAlreadyConfirmedException(BusinessLogicException):
    """Lanzada si se intenta reconfirmar un despacho ya entregado."""
    status_code = status.HTTP_409_CONFLICT
    default_detail = "Este despacho ya fue confirmado y certificado previamente con firma digital."
    default_code = "delivery_already_confirmed"
