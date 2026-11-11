"""
Utilidades auxiliares transversales (formato de códigos, conversiones de unidades).
"""

from decimal import Decimal
from django.utils import timezone


def generate_order_code(sequence_number: int) -> str:
    """Genera un código correlativo con formato DA-YYYY-XXXXX."""
    current_year = timezone.now().year
    return f"DA-{current_year}-{sequence_number:05d}"


def generate_production_code(sequence_number: int) -> str:
    """Genera un código correlativo para producción: OP-YYYY-XXXXX."""
    current_year = timezone.now().year
    return f"OP-{current_year}-{sequence_number:05d}"


def generate_dispatch_code(sequence_number: int) -> str:
    """Genera un código correlativo para despachos: DP-YYYY-XXXXX."""
    current_year = timezone.now().year
    return f"DP-{current_year}-{sequence_number:05d}"


def generate_route_code(sequence_number: int) -> str:
    """Genera un código correlativo para rutas: RT-YYYY-XXXXX."""
    current_year = timezone.now().year
    return f"RT-{current_year}-{sequence_number:05d}"


# Factores de conversión estándar al sistema base (KG para masa, LT para volumen, UNIDAD para conteo)
CONVERSION_FACTORS = {
    # Masa (Base: KG)
    ("GR", "KG"): Decimal("0.001"),
    ("KG", "KG"): Decimal("1.0"),
    ("KG", "GR"): Decimal("1000.0"),
    ("GR", "GR"): Decimal("1.0"),
    # Volumen (Base: LT)
    ("ML", "LT"): Decimal("0.001"),
    ("LT", "LT"): Decimal("1.0"),
    ("LT", "ML"): Decimal("1000.0"),
    ("ML", "ML"): Decimal("1.0"),
    # Unidades enteras
    ("UNIDAD", "UNIDAD"): Decimal("1.0"),
}


def convert_unit(quantity: Decimal, from_unit: str, to_unit: str) -> Decimal:
    """
    Convierte una cantidad entre unidades de medida compatibles.
    Lanza ValueError si no existe conversión directa definida.
    """
    if from_unit == to_unit:
        return quantity

    factor = CONVERSION_FACTORS.get((from_unit.upper(), to_unit.upper()))
    if factor is None:
        raise ValueError(f"No existe factor de conversión entre {from_unit} y {to_unit}.")

    return quantity * factor
