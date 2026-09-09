# Docker — Entorno de Desarrollo del POS

Toda la infraestructura de desarrollo local se levanta con **Docker Compose**. Incluye 4 servicios que trabajan en conjunto para emular el entorno de producción sin depender de servicios externos.

---

## Arquitectura de servicios

```
┌──────────────────────────────────────────────────────────────────────┐
│                         docker-compose.yml                          │
│                                                                      │
│   ┌──────────┐     ┌──────────┐     ┌─────────────┐                │
│   │  pos_api  │────▶│  pos_db  │     │ pos_lambda  │                │
│   │ :8000     │     │ :5432    │     │  _build     │                │
│   │ FastAPI   │     │ Postgres │     │ (one-shot)  │                │
│   └──────────┘     └──────────┘     └──────┬──────┘                │
│        │                                    │                        │
│        │            ┌───────────────────────▼──────┐                │
│        └───────────▶│       pos_localstack         │                │
│          S3 I/O     │          :4566               │                │
│                     │   S3 + Lambda (miniaturas)   │                │
│                     └──────────────────────────────┘                │
└──────────────────────────────────────────────────────────────────────┘
```

| Servicio | Contenedor | Imagen | Puerto | Descripción |
|---|---|---|---|---|
| `api` | `pos_api` | Build local (`Dockerfile`, target `runtime`) | `8000` | API FastAPI con hot-reload |
| `db` | `pos_db` | `postgres:15-alpine` | `5432` | Base de datos PostgreSQL |
| `lambda_build` | `pos_lambda_build` | `python:3.12-slim` | — | One-shot: empaqueta la Lambda de miniaturas en un zip |
| `localstack` | `pos_localstack` | `localstack/localstack:4` | `4566` | S3 local + Lambda para generación de thumbnails |

---

## Estructura de archivos

```
docker/
├── README.md              ← este archivo
├── entrypoint.sh          ← script de arranque del contenedor de la API
├── pgdata/                ← datos de PostgreSQL (bind-mount, ignorado por git)
└── localstack/
    ├── data/              ← estado persistido de LocalStack (ignorado por git)
    ├── init/
    │   └── ready.d/
    │       └── 10-init.sh ← bootstrap: crea bucket S3, despliega Lambda, conecta evento
    └── lambda/
        ├── handler.py     ← código de la Lambda de miniaturas (Pillow)
        └── requirements.txt
```

Archivos en la raíz del proyecto también relevantes:

| Archivo | Propósito |
|---|---|
| `docker-compose.yml` | Definición de todos los servicios |
| `Dockerfile` | Imagen multi-stage de la API (base → builder → runtime) |
| `.dockerignore` | Excluye archivos innecesarios del build context |
| `.env` / `.env.example` | Variables de entorno (no se commitea `.env`) |

---

## Servicios en detalle

### 1. `api` — FastAPI (pos_api)

- **Imagen**: build local multi-stage con Python 3.13-slim.
  - **Stage `builder`**: instala dependencias con `uv sync` en `/opt/venv`.
  - **Stage `runtime`**: copia el venv, crea usuario sin privilegios `app`, expone puerto 8000.
- **Entrypoint** (`docker/entrypoint.sh`):
  1. Espera activa a que PostgreSQL responda (hasta 30 intentos con `asyncpg`).
  2. Ejecuta `alembic upgrade head` para aplicar migraciones pendientes.
  3. Arranca el comando (`uvicorn` con `--reload`).
- **Hot-reload**: el directorio `.:/app` se monta como bind-mount. El venv vive en `/opt/venv`, así que el mount no pisa las dependencias.
- **Healthcheck**: `curl http://localhost:8000/health` cada 30s.
- **Dependencias**: espera a que `db` y `localstack` estén healthy antes de arrancar.
- **Variables de entorno** pisadas por Compose (no las del `.env`):
  - `DATABASE_URL` → apunta a `db:5432` (red interna de Compose).
  - `S3_ENDPOINT_URL` → `http://localstack:4566` (red interna).
  - `S3_PUBLIC_ENDPOINT_URL` → `http://localhost:4566` (para URLs firmadas que abre el navegador).

### 2. `db` — PostgreSQL (pos_db)

- **Imagen**: `postgres:15-alpine`.
- **Datos persistidos**: bind-mount en `./docker/pgdata` (sobrevive a `docker compose down` y a `down -v`).
- **Healthcheck**: `pg_isready` cada 5s, con 10 reintentos y 10s de start period.
- **Variables configurables** (con defaults):
  - `POSTGRES_USER` → `postgres`
  - `POSTGRES_PASSWORD` → `password`
  - `POSTGRES_DB` → `pos_db`

### 3. `lambda_build` — Empaquetador de Lambda (pos_lambda_build)

- **Imagen**: `python:3.12-slim` (contenedor efímero, one-shot).
- **Propósito**: compila Pillow (wheel nativo para Linux) e instala las dependencias de la Lambda en un volumen compartido (`lambda_dist`).
- **Resultado**: genera `/dist/function.zip` con `handler.py` + dependencias, listo para desplegar en LocalStack.
- **No expone puertos**. Corre una vez y termina.

### 4. `localstack` — S3 + Lambda (pos_localstack)

- **Imagen**: `localstack/localstack:4`.
- **Servicios habilitados**: `s3`, `lambda`.
- **Persistencia**: `PERSISTENCE=1` guarda el estado de S3 entre reinicios en `./docker/localstack/data/`.
- **Bootstrap** (`docker/localstack/init/ready.d/10-init.sh`):
  1. Crea el bucket `pos-imagenes` con CORS configurado (GET, PUT, HEAD).
  2. Despliega la Lambda `pos-thumbnailer` usando el zip de `lambda_build`.
  3. Conecta la notificación S3: `s3:ObjectCreated:*` con prefijo `originales/` dispara la Lambda.
- **Lambda de miniaturas** (`docker/localstack/lambda/handler.py`):
  - Se dispara cuando se sube una imagen a `originales/<dueño>/<id>/<uuid>.<ext>`.
  - Genera un thumbnail de 400×400px (conserva proporción) en `thumbnails/<dueño>/<id>/<uuid>.<ext>`.
  - Soporta JPEG, PNG y WebP. Es idempotente (sobrescribe si ya existía).
- **Dependencia**: espera a que `lambda_build` termine exitosamente.

---

## Levantar el entorno

### Prerrequisitos

- Docker y Docker Compose (v2+) instalados.
- Copiar `.env.example` a `.env` y ajustar los valores si es necesario:
  ```bash
  cp .env.example .env
  ```

### Arranque completo

```bash
# Levanta los 4 servicios (build de imagen incluido la primera vez)
docker compose up -d
```

Esto hace, en orden:
1. `lambda_build` empaqueta la Lambda (one-shot, termina rápido).
2. `db` arranca PostgreSQL y espera a estar healthy.
3. `localstack` arranca cuando `lambda_build` terminó; crea bucket, despliega Lambda.
4. `api` arranca cuando `db` y `localstack` están healthy; aplica migraciones y levanta uvicorn.

### Reconstruir la imagen de la API (tras cambiar dependencias)

```bash
docker compose build api
docker compose up -d api
```

### Ver logs

```bash
# Todos los servicios
docker compose logs -f

# Solo la API
docker compose logs -f api

# Solo LocalStack (para ver si la Lambda se desplegó bien)
docker compose logs -f localstack
```

### Detener los servicios

```bash
# Detener sin eliminar contenedores
docker compose stop

# Detener y eliminar contenedores (los datos de Postgres y S3 se conservan)
docker compose down

# Detener, eliminar contenedores y el volumen scratch de lambda_dist
docker compose down -v
```

> **Nota**: `docker compose down -v` **no** borra los datos de PostgreSQL ni de S3 porque son bind-mounts (`./docker/pgdata/` y `./docker/localstack/data/`), no named volumes.

### Borrar datos completamente (reset total)

```bash
docker compose down -v
rm -rf docker/pgdata docker/localstack/data
docker compose up -d
```

Esto recrea la base de datos desde cero (las migraciones se reaplicarán automáticamente al arrancar).

---

## Variables de entorno relevantes

| Variable | Default | Dónde se usa | Descripción |
|---|---|---|---|
| `POSTGRES_USER` | `postgres` | `db`, `api` | Usuario de PostgreSQL |
| `POSTGRES_PASSWORD` | `password` | `db`, `api` | Contraseña de PostgreSQL |
| `POSTGRES_DB` | `pos_db` | `db`, `api` | Nombre de la base de datos |
| `DATABASE_URL` | ver `.env.example` | `api` | Connection string (Compose la pisa con host `db`) |
| `S3_ENDPOINT_URL` | `http://localhost:4566` | `api` | Endpoint S3 (Compose la pisa con `http://localstack:4566`) |
| `S3_PUBLIC_ENDPOINT_URL` | `http://localhost:4566` | `api` | Endpoint para URLs firmadas (accesible desde el navegador) |
| `S3_BUCKET_IMAGENES` | `pos-imagenes` | `api`, `localstack` | Nombre del bucket de imágenes |
| `AWS_ACCESS_KEY_ID` | `test` | `api` | Credencial AWS (ficticia para LocalStack) |
| `AWS_SECRET_ACCESS_KEY` | `test` | `api` | Credencial AWS (ficticia para LocalStack) |

---

## Puertos expuestos

| Puerto | Servicio | Uso |
|---|---|---|
| `8000` | API FastAPI | `http://localhost:8000` — Docs en `/docs` |
| `5432` | PostgreSQL | Conexión directa con cliente SQL (DBeaver, pgAdmin, etc.) |
| `4566` | LocalStack | S3 local — `http://localhost:4566` |

---

## Flujo de imágenes (S3 + Lambda)

```
                                      ┌──────────────────────┐
 API sube imagen                     │   Bucket S3            │
 ──────────────────▶  originales/    │   pos-imagenes         │
                     <dueño>/<id>/   │                        │
                     <uuid>.jpg      │                        │
                                      └──────────┬───────────┘
                                                  │ s3:ObjectCreated
                                                  ▼
                                      ┌──────────────────────┐
                                      │ Lambda pos-thumbnailer│
                                      │   Pillow resize       │
                                      │   400×400 max         │
                                      └──────────┬───────────┘
                                                  │ PUT
                                                  ▼
                                      ┌──────────────────────┐
                                      │  thumbnails/          │
                                      │  <dueño>/<id>/        │
                                      │  <uuid>.jpg           │
                                      └──────────────────────┘
```

---

## Troubleshooting

### La API no arranca / "Base no lista"
- Verificar que `db` esté corriendo: `docker compose ps db`
- Ver logs de la base: `docker compose logs db`
- El entrypoint reintenta 30 veces cada 2 segundos antes de fallar.

### El bucket S3 no se crea
- Ver logs de LocalStack: `docker compose logs localstack`
- Verificar que el script `10-init.sh` ejecutó: buscar líneas `[init]` en los logs.

### La Lambda no genera miniaturas
- Verificar que `lambda_build` terminó bien: `docker compose logs lambda_build`
- Si el zip no se generó, el init lo salta con un aviso (la API funciona sin miniaturas).
- Probar manualmente: `docker compose exec localstack awslocal lambda invoke --function-name pos-thumbnailer --payload '{}' /tmp/out.json`

### Datos corruptos / quiero empezar de cero
```bash
docker compose down -v
rm -rf docker/pgdata docker/localstack/data
docker compose up -d
```
