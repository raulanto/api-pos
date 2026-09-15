# Docker — Entorno de Desarrollo del POS

Toda la infraestructura de desarrollo local se levanta con **Docker Compose**. Son 2 servicios: la API y PostgreSQL. Las imágenes subidas se guardan en disco (dentro del propio bind-mount de la API), sin infra aparte.

---

## Arquitectura de servicios

```
┌──────────────────────────────────────┐
│           docker-compose.yml          │
│                                        │
│   ┌──────────┐     ┌──────────┐      │
│   │  pos_api  │────▶│  pos_db  │      │
│   │ :8000     │     │ :5432    │      │
│   │ FastAPI   │     │ Postgres │      │
│   └──────────┘     └──────────┘      │
└────────────────────────────────────────┘
```

| Servicio | Contenedor | Imagen | Puerto | Descripción |
|---|---|---|---|---|
| `api` | `pos_api` | Build local (`Dockerfile`, target `runtime`) | `8000` | API FastAPI con hot-reload |
| `db` | `pos_db` | `postgres:15-alpine` | `5432` | Base de datos PostgreSQL |

---

## Estructura de archivos

```
docker/
├── README.md              ← este archivo
├── entrypoint.sh          ← script de arranque del contenedor de la API
└── pgdata/                ← datos de PostgreSQL (bind-mount, ignorado por git)
```

Archivos en la raíz del proyecto también relevantes:

| Archivo | Propósito |
|---|---|
| `docker-compose.yml` | Definición de todos los servicios |
| `Dockerfile` | Imagen multi-stage de la API (base → builder → runtime) |
| `.dockerignore` | Excluye archivos innecesarios del build context |
| `.env` / `.env.example` | Variables de entorno (no se commitea `.env`) |
| `media/` | Imágenes subidas por la API (bind-mount vía `.:/app`, ignorado por git) |

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
- **Hot-reload**: el directorio `.:/app` se monta como bind-mount. El venv vive en `/opt/venv`, así que el mount no pisa las dependencias. Las imágenes subidas quedan en `./media` dentro de ese mismo bind-mount.
- **Healthcheck**: `curl http://localhost:8000/health` cada 30s.
- **Dependencias**: espera a que `db` esté healthy antes de arrancar.
- **Variables de entorno** pisadas por Compose (no las del `.env`):
  - `DATABASE_URL` → apunta a `db:5432` (red interna de Compose).

### 2. `db` — PostgreSQL (pos_db)

- **Imagen**: `postgres:15-alpine`.
- **Datos persistidos**: bind-mount en `./docker/pgdata` (sobrevive a `docker compose down` y a `down -v`).
- **Healthcheck**: `pg_isready` cada 5s, con 10 reintentos y 10s de start period.
- **Variables configurables** (con defaults):
  - `POSTGRES_USER` → `postgres`
  - `POSTGRES_PASSWORD` → `password`
  - `POSTGRES_DB` → `pos_db`

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
# Levanta los 2 servicios (build de imagen incluido la primera vez)
docker compose up -d
```

Esto hace, en orden:

1. `db` arranca PostgreSQL y espera a estar healthy.
2. `api` arranca cuando `db` está healthy; aplica migraciones y levanta uvicorn.

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
```

### Detener los servicios

```bash
# Detener sin eliminar contenedores
docker compose stop

# Detener y eliminar contenedores (los datos de Postgres y las imágenes se conservan)
docker compose down
```

> **Nota**: los datos de PostgreSQL (`./docker/pgdata/`) y las imágenes subidas (`./media/`) son bind-mounts, no named volumes — `docker compose down -v` no los borra.

### Borrar datos completamente (reset total)

```bash
docker compose down
rm -rf docker/pgdata media
docker compose up -d
```

Esto recrea la base de datos desde cero (las migraciones se reaplicarán automáticamente al arrancar) y vacía las imágenes subidas.

---

## Variables de entorno relevantes

| Variable | Default | Dónde se usa | Descripción |
|---|---|---|---|
| `POSTGRES_USER` | `postgres` | `db`, `api` | Usuario de PostgreSQL |
| `POSTGRES_PASSWORD` | `password` | `db`, `api` | Contraseña de PostgreSQL |
| `POSTGRES_DB` | `pos_db` | `db`, `api` | Nombre de la base de datos |
| `DATABASE_URL` | ver `.env.example` | `api` | Connection string (Compose la pisa con host `db`) |
| `MEDIA_ROOT` | `media` | `api` | Carpeta en disco donde se guardan las imágenes |
| `MEDIA_BASE_URL` | `/media` | `api` | Prefijo bajo el que la API sirve esa carpeta como estático |

---

## Puertos expuestos

| Puerto | Servicio | Uso |
|---|---|---|
| `8000` | API FastAPI | `http://localhost:8000` — Docs en `/docs` |
| `5432` | PostgreSQL | Conexión directa con cliente SQL (DBeaver, pgAdmin, etc.) |

---

## Flujo de imágenes (disco local)

Ver `docs/imagenes-almacenamiento-local.md`: la API guarda el original en
`media/originales/<dueño>/<id>/<uuid>.ext` y genera la miniatura (Pillow,
400×400 máx.) en `media/thumbnails/...` en el mismo request de subida — sin
servicios externos.

---

## Troubleshooting

### La API no arranca / "Base no lista"
- Verificar que `db` esté corriendo: `docker compose ps db`
- Ver logs de la base: `docker compose logs db`
- El entrypoint reintenta 30 veces cada 2 segundos antes de fallar.

### Datos corruptos / quiero empezar de cero
```bash
docker compose down
rm -rf docker/pgdata media
docker compose up -d
```
