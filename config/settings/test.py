"""Configuración aislada para ejecutar pruebas sin un servidor PostgreSQL local."""

from .base import *

DEBUG = False

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}
