# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# Base: Python 3.13 (coincide con .python-version y requires-python del proyecto)
# ---------------------------------------------------------------------------
FROM python:3.13-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    # uv: entorno del proyecto fuera de /app para que el bind-mount de dev
    # (compose monta .:/app) no pise las dependencias instaladas.
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never \
    PATH="/opt/venv/bin:$PATH"

# ---------------------------------------------------------------------------
# Builder: instala dependencias en /opt/venv (capa cacheable)
# ---------------------------------------------------------------------------
FROM base AS builder

# uv pinneado (subir de versión de forma consciente, no con :latest)
COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /uvx /bin/

WORKDIR /app

# Solo depende de los manifiestos -> la capa se reutiliza si no cambian.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    uv sync --frozen --no-install-project --no-dev

# ---------------------------------------------------------------------------
# Runtime: imagen final, sin uv ni toolchain de build
# ---------------------------------------------------------------------------
FROM base AS runtime

# curl para el HEALTHCHECK; usuario sin privilegios para correr la app.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system app \
    && useradd --system --gid app --home-dir /app app

WORKDIR /app

COPY --from=builder --chown=app:app /opt/venv /opt/venv
COPY --chown=app:app . .

RUN chmod +x /app/docker/entrypoint.sh

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

# El entrypoint aplica `alembic upgrade head` (esquema + seeder) antes de arrancar.
ENTRYPOINT ["/app/docker/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
