# POS Backend API

API REST para un Sistema de Punto de Venta (POS) multi-sucursal construida con **FastAPI**, **SQLAlchemy** (async) y **PostgreSQL**. La arquitectura sigue una estructura de **Modular Monolith** enfocada en Clean Architecture por dominio.

---

## ¿Qué hace esta API?

Esta API gestiona las operaciones centrales de uno o varios puntos de venta:

* **Inventario y Productos:** Gestión de productos, categorías, imágenes, existencias por sucursal y registro automático de movimientos de stock.
* **Ventas y Caja:** Procesamiento de ventas, apertura y cierre de turnos de caja (arqueo/cierre con diferencias), congelamiento de precios e impuestos al vender.
* **Clientes y Promociones:** Gestión de catálogo de clientes, promociones temporales y descuentos por sucursal.
* **Proveedores y Compras:** Gestión de proveedores, pedidos de compra, recepciones de mercancía e insumos, y devoluciones.
* **Usuarios, Roles y Permisos (RBAC):** Autenticación mediante JWT, asignación de permisos por rol y control de acceso granular por sucursal.
* **Reportes y PDF/Excel:** Generación de reportes de ventas, arqueos y exportación de documentos (PDF, Excel).
* **Auditoría:** Registro de eventos in-process para trazabilidad de operaciones críticas.

---

## Requisitos previos

* **Docker** y **Docker Compose** (recomendado)
* **Python 3.12+** (si se ejecuta sin Docker)
* **uv** o `pip` (gestor de paquetes de Python)
* **PostgreSQL** (si se ejecuta sin Docker)

---

## Configuración inicial de variables de entorno

Antes de ejecutar la aplicación (con o sin Docker), copia el archivo `.env.example` a `.env`:

```bash
cp .env.example .env
```

---

## Opción 1: Ejecutar con Docker (Recomendado)

Docker levantará tanto la API FastAPI como la base de datos PostgreSQL. Las migraciones de base de datos se ejecutan automáticamente al iniciar la API.

### 1. Iniciar los contenedores

```bash
docker-compose up -d --build
```

Esto iniciará:
* **`pos_db`**: Base de datos PostgreSQL en `localhost:5432`.
* **`pos_api`**: Servidor FastAPI en `localhost:8000` con hot-reload activado.

### 2. Verificar estado y logs

```bash
docker-compose logs -f api
```

### 3. Detener los servicios

```bash
docker-compose down
```

---

## Opción 2: Ejecutar sin Docker (Desarrollo local)

Para ejecutar la API directamente en tu máquina local, necesitarás un servidor PostgreSQL activo.

### 1. Levantar solo la Base de Datos con Docker Compose

Si no tienes un Postgres local instalado, puedes levantar únicamente el servicio de base de datos:

```bash
docker-compose up -d db
```

### 2. Crear entorno virtual e instalar dependencias

Usando **`uv`** (recomendado):
```bash
uv sync
source .venv/bin/activate
```

O usando `venv` estándar:
```bash
python -m venv .venv
source .venv/bin/activate  # En Windows: .venv\Scripts\activate
pip install -r pyproject.toml
```

### 3. Aplicar migraciones de la base de datos

```bash
alembic upgrade head
```

### 4. Iniciar el servidor de desarrollo

```bash
uvicorn app.main:app --reload --port 8000
```

---

## Documentación de la API

Una vez levantada la aplicación, puedes acceder a la documentación interactiva de la API en:

* **Swagger UI:** [http://localhost:8000/docs](http://localhost:8000/docs)
* **ReDoc:** [http://localhost:8000/redoc](http://localhost:8000/redoc)
* **Health Check:** [http://localhost:8000/health](http://localhost:8000/health)

---

## Pruebas Unitarias e Integración

Para ejecutar los tests de la suite con `pytest`:

```bash
# Con uv
uv run pytest

# Con entorno virtual activado
pytest
```