"""
Validadores reutilizables del dominio para Dulce Arte.
"""

import re
from django.core.exceptions import ValidationError


def clean_rut(rut: str) -> str:
    """Limpia caracteres de formato (puntos y guiones) de un RUT."""
    return re.sub(r"[^0-9kK]", "", str(rut)).upper()


def calculate_rut_dv(rut_number: int) -> str:
    """Calcula el dígito verificador para un cuerpo de RUT mediante módulo 11."""
    reversed_digits = [int(d) for d in reversed(str(rut_number))]
    factors = [2, 3, 4, 5, 6, 7]
    s = sum(d * factors[i % len(factors)] for i, d in enumerate(reversed_digits))
    remainder = 11 - (s % 11)
    if remainder == 11:
        return "0"
    if remainder == 10:
        return "K"
    return str(remainder)


def validate_rut_or_dni(value: str):
    """
    Valida un documento de identidad.
    Si tiene formato de RUT chileno (números con dígito verificador), valida el dígito verificador.
    En caso de documento internacional / DNI, valida longitud mínima y formato alfanumérico.
    """
    if not value or not str(value).strip():
        raise ValidationError("El número de identificación no puede estar vacío.")

    cleaned = clean_rut(value)
    if len(cleaned) < 5 or len(cleaned) > 20:
        raise ValidationError("El documento de identidad debe tener entre 5 y 20 caracteres.")

    # Si parece un RUT chileno (cuerpo numérico + DV dígito o K, entre 7 y 9 caracteres)
    if re.match(r"^\d{6,8}[0-9K]$", cleaned):
        body = int(cleaned[:-1])
        expected_dv = calculate_rut_dv(body)
        given_dv = cleaned[-1]
        if expected_dv != given_dv:
            raise ValidationError(f"El RUT ingresado '{value}' es inválido (dígito verificador incorrecto).")
