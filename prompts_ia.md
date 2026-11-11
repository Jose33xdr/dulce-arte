# Bitácora de Interacciones y Prompts de Asistencia con IA
## Proyecto: Dulce Arte — Sistema Web de Trazabilidad, Producción, Inventario y Despacho

Este documento registra de forma transparente y auditable el soporte de Inteligencia Artificial utilizado durante las fases del proyecto, cumpliendo con los estándares de integridad académica.

---

### Registro N.º 1 — Fase 1: Análisis Funcional y Diseño de Arquitectura
* **Fecha:** 2026-11-06
* **Rol Asumido:** Arquitecto de Software Senior & Diseñador Fullstack UX/UI.
* **Instrucción del Usuario:**
  > Actúa como un arquitecto de software senior... Vamos a desarrollar desde cero un proyecto académico llamado Dulce Arte... Stack obligatorio: Python, Django, DRF, PostgreSQL, Django Templates, Tailwind CSS, Admin personalizado, sesiones Django, AWS EC2. Comienza únicamente con la FASE 1: Análisis funcional, arquitectura propuesta, estructura de directorios, modelos/relaciones, matriz RBAC, endpoints REST, plan de implementación y criterios de aceptación. No implementes código todavía.
* **Aportes y Soluciones de la IA:**
  1. Diseño del flujo de valor integral (*End-to-End*) desde cotización hasta entrega con firma digital.
  2. Diagrama de arquitectura modular monolítica con desacoplamiento estricto mediante la capa de servicios (`Service Layer Pattern`).
  3. Formulación de las 6 reglas de negocio críticas (*invariants*): identificación única `DA-YYYY-XXXXX`, no negatividad de stock, consumo atómico con `select_for_update()`, protección anti-doble consumo con flag `stock_consumed`, trazabilidad histórica inmutable y entrega con firma digital idempotente.
  4. Especificación del Modelo Entidad-Relación (MER) con 11 entidades y restricciones de integridad (`CheckConstraint`, `UniqueConstraint`).
  5. Matriz RBAC para los 4 roles requeridos: `ADMIN`, `VENTAS`, `COCINA`, `REPARTIDOR`.
  6. Especificación de endpoints REST v1 con estándares de verbos HTTP y códigos de estado.
  7. Plan de desarrollo en 7 fases y criterios de aceptación en formato BDD/Gherkin.

---

### Registro N.º 2 — Fase 2: Ajustes de Arquitectura e Implementación Inicial
* **Fecha:** 2026-11-06
* **Rol Asumido:** Arquitecto de Software Senior y Desarrollador Especializado en Django, DRF y PostgreSQL.
* **Instrucción del Usuario:**
  > Continuemos con Dulce Arte. La Fase 1 queda APROBADA CON AJUSTES: 1. Rutas de despacho mediante DeliveryRoute y paradas ordenadas; 2. Conversión consistente de unidades de medida; 3. Soporte para personalizaciones de pedidos; 4. CRUD con eliminación protegida (Soft Delete); 5. Protección CSRF, autenticación por sesiones y RBAC en API y Web; 6. Validación atómica de stock y bloqueo de filas; 7. Diferenciar estados comerciales de etapas de cocina; 8. Mantener implementación sencilla y académica. Implementar Fase 2: entorno virtual, Django, DRF, PostgreSQL real (no SQLite), modelo Custom User antes de migraciones, Django Admin personalizado, Frontend base con tokens de diseño, documentación y verificación real de inicio.
* **Aportes y Soluciones de la IA:**
  1. **Inspección de Infraestructura:** Detección de PostgreSQL 16 y Python 3.14 en el sistema local.
  2. **Configuración de Base de Datos Real:** Puesta en marcha del servicio PostgreSQL, verificación de credenciales locales y creación de la base de datos `dulce_arte_db`.
  3. **Instalación de Dependencias:** Creación del entorno virtual `.venv` e instalación de `Django 6.1.3`, `djangorestframework 3.18.3`, `psycopg 3.3.8` (adaptador oficial moderno de PostgreSQL), `python-dotenv 1.2.4`, `pillow 13.0.0` y `django-cors-headers 4.9.0`.
  4. **Modularización Limpia:** Estructura de 9 aplicaciones modulares (`core`, `users`, `clients`, `inventory`, `recipes`, `orders`, `production`, `dispatch`, `dashboard`) desacopladas bajo la carpeta `apps/`.
  5. **Modelos Abstractos de Integridad (`core`):** Creación de `TimeStampedModel` y `SoftDeleteModel` para desactivación lógica y auditoría histórica no destructiva.
  6. **Motor de Conversión de Unidades (`core.utils`):** Implementación de utilidades para cálculo entre gramos/kilogramos, mililitros/litros y unidades.
  7. **Modelo Custom User Pre-Migración (`users.models.User`):** Definición del modelo heredado de `AbstractUser` con enumeración `UserRole` (`ADMIN`, `VENTAS`, `COCINA`, `REPARTIDOR`) y propiedades booleanas (`is_admin`, `is_sales`, etc.), evitando errores irreparables en el ciclo de vida del ORM.
  8. **Seguridad y Permisos RBAC (`users.permissions`):** Clases de permisos para DRF (`IsAdminRole`, `IsSalesRole`, etc.) y mixins/decoradores para Django Web (`RoleRequiredMixin`, `@role_required`).
  9. **Frontend Atómico & Tokens Semánticos:**
     - Archivo `static/css/theme.css` con variables CSS para la paleta institucional:
       - Fondo principal: `#FAF7F2`
       - Burdeos principal: `#773344`
       - Rosa pastel: `#F3D6DB`
       - Verde suave: `#DCEBDD`
       - Texto oscuro: `#292524`
     - Plantilla base `templates/base.html`, componentes modulares `sidebar.html` y `topbar.html`, y pantallas operativas `login.html` y `dashboard/index.html`.
  10. **Verificación y Pruebas Reales:** Creación y ejecución de la suite de pruebas automatizadas `tests/test_initial_setup.py` (8 pruebas ejecutadas en 18.36s contra PostgreSQL con resultado exitoso 100%).

---

### Registro N.º 3 — Fase 3: Modelado Relacional, Migraciones y Django Admin
* **Fecha:** 2026-11-06
* **Rol Asumido:** Arquitecto Senior especializado en Django ORM, PostgreSQL, Integridad Referencial y Diseño Administrativo.
* **Instrucción del Usuario:**
  > Continuemos con el proyecto Dulce Arte... Ejecutar la FASE 3: Modelado Relacional, Migraciones y Django Admin... 1. Auditoría previa obligatoria; 2. Modelos del dominio: Clientes (Client), Inventario (Supply, UnitOfMeasure, StockMovement), Productos y Recetas (Product, Recipe, RecipeIngredient), Pedidos (Order, OrderItem, OrderStatusHistory), Producción (ProductionOrder, QualityCheck), Despachos (DeliveryRoute, DispatchOrder, DeliveryProof); 3. Integridad de datos: ForeignKey/OneToOne, UniqueConstraint, CheckConstraint, DecimalField para dinero/cantidades, índices, PROTECT, eliminación lógica, unidades compatibles, no poner consumo en save(); 4. Django Admin profesional: list_display, list_filter, search_fields, inlines tabulares, badges visuales, inmutabilidad de movimientos e historial; 5. Migraciones en PostgreSQL; 6. Pruebas automatizadas completas; 7. Actualización de documentación.
* **Aportes y Soluciones de la IA:**
  1. **Auditoría Previa Exitosa:** Verificación de `check` (0 issues), conexión a PostgreSQL 16 y ejecución de la suite base (8/8 pruebas exitosas).
  2. **Implementación de Modelos del Dominio:**
     - `clients.Client`: Validación de RUT chileno (módulo 11) y DNI internacional, normalización y `SoftDeleteModel`.
     - `inventory.UnitOfMeasure`: Conversión consistente de magnitudes (`MASA`, `VOLUMEN`, `UNIDAD`) con factores hacia unidades base.
     - `inventory.Supply`: Insumos con `CheckConstraint` de no negatividad para stock actual, mínimo y costo unitario.
     - `inventory.StockMovement`: Historial de solo anexado (`ENTRADA`, `SALIDA_MANUAL`, `CONSUMO_PRODUCCION`, `AJUSTE_MERMA`, `DEVOLUCION`) con bloqueo de edición/eliminación en Django Admin.
     - `recipes.Product`: Catálogo de productos con categoría, precio base y tiempo de producción.
     - `recipes.Recipe` & `RecipeIngredient`: BOM con porcentaje de merma, cálculo de cantidad bruta efectiva, conversión a unidad base del insumo y validación estricta de magnitudes compatibles en `clean()`.
     - `orders.Order`: Código único `DA-YYYY-XXXXX`, estados comerciales desacoplados de cocina, cálculo de saldo pendiente y restricción `deposit_amount <= total_amount`.
     - `orders.OrderItem`: Personalización artesanal (porciones, sabor de bizcocho, relleno, cubierta, dedicatoria, detalles) con subtotales en `DecimalField`.
     - `orders.OrderStatusHistory`: Bitácora histórica inmutable vinculada al usuario responsable.
     - `production.ProductionOrder`: Etapas Kanban (`RECIBIDO`, `EN_PREPARACION`, `HORNEADO_DECORADO`, `CONTROL_CALIDAD`, `LISTO`), cocinero asignado y flag de seguridad `stock_consumed` anti-duplicados.
     - `production.QualityCheck`: Evaluación de conformidad previa a entrega.
     - `dispatch.DeliveryRoute`: Rutas programadas por fecha y repartidor.
     - `dispatch.DispatchOrder`: Paradas ordenadas (`stop_order`) con restricción de unicidad de secuencia en ruta (`UniqueConstraint(fields=['route', 'stop_order'])`).
     - `dispatch.DeliveryProof`: Certificación de entrega con firma digital (DataURI) y receptor.
  3. **Compatibilidad Django 6+:** Identificación y adaptación proactiva de `CheckConstraint(condition=Q(...))` reemplazando el argumento deprecado `check=...`.
  4. **Django Admin Profesional:** Inlines tabulares (`RecipeIngredientInline`, `OrderItemInline`, `OrderStatusHistoryInline`, `QualityCheckInline`, `DispatchOrderInline`), badges visuales HTML para estados y bloqueo de edición en tablas de auditoría.
  5. **Migraciones:** Creación y aplicación limpia de 6 archivos de migración inicial en PostgreSQL sin modificar bases de datos existentes.
  6. **Suite de Pruebas Completa:** Creación de 12 pruebas de integridad y ejecución conjunta con las 8 de Fase 2, alcanzando 20 pruebas ejecutadas en 15.91s con 100% de éxito.

---

### Registro N.º 4 — Fase 4: Capa de Servicios y Reglas de Negocio
* **Fecha:** 2026-11-__ *(completar)*
* **Instrucción del Usuario:**
  > *(Pegar aquí el prompt real o resumirlo)* Implementar la lógica de negocio en una capa de servicios: creación y confirmación de pedidos, flujo Kanban de producción, descuento de insumos por receta (BOM) y gestión de rutas de despacho.
* **Aportes y Soluciones de la IA:**
  1. `OrderService`: creación de pedidos, confirmación (genera orden de producción y despacho) y cancelación con historial de estados.
  2. `ProductionService`: transiciones de etapa Kanban, control de calidad obligatorio antes de quedar "Listo" y asignación de cocinero.
  3. `InventoryService`: verificación de disponibilidad, entradas, mermas y descuento atómico de insumos con `select_for_update()`; el flag `stock_consumed` evita el doble descuento.
  4. `DispatchService`: creación de rutas, asignación de paradas, inicio de ruta y confirmación de entrega con firma digital.

---

### Registro N.º 5 — Fase 5: API REST v1 y Permisos por Rol
* **Fecha:** 2026-11-__ *(completar)*
* **Instrucción del Usuario:**
  > *(Pegar aquí el prompt real o resumirlo)* Exponer los módulos como API REST bajo `/api/v1/` con autenticación por sesión y permisos según rol.
* **Aportes y Soluciones de la IA:**
  1. Serializers y vistas DRF para clientes, inventario, recetas, pedidos, producción, despacho y dashboard.
  2. Autenticación por sesión (`SessionAuthentication`) y `IsAuthenticated` por defecto, con permisos por rol (`ADMIN`, `VENTAS`, `COCINA`, `REPARTIDOR`).
  3. Validación de identificadores, paginación y manejo uniforme de errores de negocio.

---

### Registro N.º 6 — Fase 6: Interfaz Web (Templates)
* **Fecha:** 2026-11-__ *(completar)*
* **Instrucción del Usuario:**
  > *(Pegar aquí el prompt real o resumirlo)* Crear la interfaz web con Django Templates: login, dashboard con métricas y pantallas de consulta por módulo.
* **Aportes y Soluciones de la IA:**
  1. `base.html` con componentes `sidebar` y `topbar`, y pantallas `login`, `dashboard/index` y `dashboard/module`.
  2. Vistas protegidas con `LoginRequiredMixin` y métricas operativas desde `DashboardService`.

---

### Registro N.º 7 — Fase 7: Pruebas y Documentación
* **Fecha:** 2026-11-__ *(completar)*
* **Instrucción del Usuario:**
  > *(Pegar aquí el prompt real o resumirlo)* Ampliar la suite de pruebas, verificar el flujo completo y actualizar el README.
* **Aportes y Soluciones de la IA:**
  1. Suite de 55 pruebas automatizadas (integridad, reglas de negocio, API, roles y flujo completo).
  2. Actualización del README con el MER, restricciones y ejecución de pruebas.

---

### Registro N.º 8 — Django Admin con Templates
* **Fecha:** 2026-11-10
* **Instrucción del Usuario:**
  > Mantengámoslo simple, que tenga lo esencial de la rúbrica.
* **Aportes y Soluciones de la IA:**
  1. Revisión del proyecto contra la rúbrica de la Evaluación 3.
  2. Se propuso personalizar el Admin; en la revisión posterior se detectó que las plantillas estaban guardadas con extensión `.txt` y una estaba vacía, y se corrigieron en el Registro N.º 9.

---

### Registro N.º 9 — Revisión de la Evaluación y Preparación de Despliegue
* **Fecha:** 2026-11-10
* **Instrucción del Usuario:**
  > El proyecto está basado en la actividad; completar lo necesario para cumplir la rúbrica y mantener el código sencillo.
* **Aportes y Soluciones de la IA:**
  1. Comparación de la implementación con la pauta, comprobación de migraciones y ejecución de las 55 pruebas con una configuración aislada de SQLite en memoria.
  2. Activación de las plantillas de marca e índice del Django Admin con los nombres que Django reconoce (`admin/base_site.html` y `admin/index.html`).
  3. Preparación de Gunicorn, Nginx y un servicio systemd para EC2, más instrucciones de configuración PostgreSQL.
  4. Despliegue en Ubuntu 26.04 con PostgreSQL 18, Gunicorn y Nginx; migraciones y archivos estáticos aplicados, y página de inicio de sesión del Admin verificada por HTTP 200 en `http://100.48.94.162/admin/login/`.
  5. Configuración de acceso HTTP por IP pública, sin HTTPS ni DNS, según la decisión del usuario. Los secretos de producción se generaron en la instancia y no se incluyeron en el repositorio ni en el paquete desplegado.

---

### Registro N.º 10 — Simplificación de la Interfaz
* **Fecha:** 2026-11-11
* **Instrucción del Usuario:**
  > Dejar el diseño visualmente simple y conservar lo importante.
* **Aportes y Soluciones de la IA:**
  1. Se simplificaron la navegación, el inicio de sesión y el resumen principal, conservando las métricas y enlaces operativos.
  2. Se retiraron elementos visuales y controles sin función para facilitar el uso y mantenimiento.
