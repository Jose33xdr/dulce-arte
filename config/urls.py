"""
Enrutador principal del sistema Dulce Arte.
Mapea rutas de administración, autenticación, interfaz web y API REST v1.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

# Personalización institucional del Django Admin
admin.site.site_header = "Dulce Arte — Administración"
admin.site.site_title = "Dulce Arte"
admin.site.index_title = "Panel de Control Operativo"

urlpatterns = [
    # Administración oficial de Django
    path("admin/", admin.site.urls),
    # Autenticación y cuentas de usuario
    path("auth/", include("apps.users.urls")),
    # Módulo Dashboard principal
    path("", include("apps.dashboard.urls")),
    # ─── API REST v1 ──────────────────────────────────────────────────────────
    path("api/v1/auth/", include("apps.users.api.urls")),
    path("api/v1/clients/", include("apps.clients.api.urls")),
    path("api/v1/inventory/", include("apps.inventory.api.urls")),
    path("api/v1/", include("apps.recipes.api.urls")),
    path("api/v1/orders/", include("apps.orders.api.urls")),
    path("api/v1/", include("apps.production.api.urls")),
    path("api/v1/dispatch/", include("apps.dispatch.api.urls")),
    path("api/v1/dashboard/", include("apps.dashboard.api.urls")),
]

# Servir archivos estáticos y media en entorno de desarrollo
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
