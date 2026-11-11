"""
Configuración de desarrollo local para Dulce Arte.
Usa base de datos PostgreSQL local y herramientas de depuración.
"""

import os
from .base import *

DEBUG = True

# Base de datos PostgreSQL local
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("DB_NAME", "dulce_arte_db"),
        "USER": os.getenv("DB_USER", "postgres"),
        "PASSWORD": os.getenv("DB_PASSWORD", "postgres"),
        "HOST": os.getenv("DB_HOST", "127.0.0.1"),
        "PORT": os.getenv("DB_PORT", "5432"),
        "CONN_MAX_AGE": 60,
    }
}

# Backend de correo en consola para desarrollo
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
