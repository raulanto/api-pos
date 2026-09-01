#!/bin/sh
set -e

# Espera activa a la base (por si el healthcheck de compose no alcanzó).
echo "[entrypoint] Verificando conexión a la base de datos..."
python - <<'PY'
import os, sys, time
import asyncio
import asyncpg

url = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")

async def wait():
    for intento in range(1, 31):
        try:
            conn = await asyncpg.connect(url)
            await conn.close()
            print(f"[entrypoint] Base disponible (intento {intento}).")
            return
        except Exception as exc:  # noqa: BLE001
            print(f"[entrypoint] Base no lista ({exc}); reintentando...")
            time.sleep(2)
    print("[entrypoint] La base no respondió a tiempo.", file=sys.stderr)
    sys.exit(1)

asyncio.run(wait())
PY

echo "[entrypoint] Aplicando migraciones (alembic upgrade head)..."
alembic upgrade head

echo "[entrypoint] Iniciando: $*"
exec "$@"
