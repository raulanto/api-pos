"""Storage de la imagen de fachada de una sucursal.

Reusa el almacén local del proyecto (`app/core/media_storage.py`) sin
abstracción nueva. Misma carpeta que las imágenes de producto
(`settings.media_root`), prefijo `sucursales/`. No pasa por `originales/`, así
que el adapter de inventario no le genera miniatura (las fachadas no tienen).
"""
from uuid import UUID, uuid4

from fastapi.concurrency import run_in_threadpool

from app.core import media_storage

PREFIJO = "sucursales/"

# content-type -> extensión. También hace de allowlist.
EXTENSIONES_PERMITIDAS: dict[str, str] = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


def content_type_valido(content_type: str) -> bool:
    return (content_type or "").split(";")[0].strip().lower() in EXTENSIONES_PERMITIDAS


def nueva_key(sucursal_id: UUID, content_type: str) -> str:
    ext = EXTENSIONES_PERMITIDAS[content_type.split(";")[0].strip().lower()]
    return f"{PREFIJO}{sucursal_id}/{uuid4().hex}{ext}"


async def subir(key: str, contenido: bytes, content_type: str) -> None:
    await run_in_threadpool(media_storage.guardar, key, contenido)


async def eliminar(key: str) -> None:
    await run_in_threadpool(media_storage.borrar, key)


def url_publica(key: str) -> str:
    return media_storage.url_publica(key)
