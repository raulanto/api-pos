"""Adapter de filesystem local (Pillow) del puerto `AlmacenImagenes`.

Reemplaza al adapter S3/LocalStack: no hay object storage ni Lambda de
miniaturas. Al guardar un original (`originales/...`) genera acá mismo, en el
momento, la miniatura correspondiente (`thumbnails/...`) con Pillow.

El disco es I/O bloqueante: cada operación corre en el threadpool de
Starlette para no bloquear el event loop.
"""
import io
import logging

from fastapi.concurrency import run_in_threadpool
from PIL import Image

from app.core import media_storage
from app.modules.inventario.application.ports.almacen_imagenes import (
    AlmacenImagenes, PREFIJO_ORIGINALES,
)

logger = logging.getLogger(__name__)

MINIATURA_TAMANO = (400, 400)


class LocalAlmacenImagenes(AlmacenImagenes):
    async def subir(self, contenido: bytes, content_type: str, key: str) -> None:
        await run_in_threadpool(self._guardar_con_miniatura, contenido, key)

    def _guardar_con_miniatura(self, contenido: bytes, key: str) -> None:
        media_storage.guardar(key, contenido)
        if key.startswith(PREFIJO_ORIGINALES):
            self._generar_miniatura(contenido, key)

    def _generar_miniatura(self, contenido: bytes, key: str) -> None:
        try:
            with Image.open(io.BytesIO(contenido)) as img:
                formato = img.format or "JPEG"
                img.thumbnail(MINIATURA_TAMANO)
                if formato == "JPEG" and img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")
                buffer = io.BytesIO()
                img.save(buffer, format=formato)
            media_storage.guardar(AlmacenImagenes.key_miniatura(key), buffer.getvalue())
        except Exception:
            # Best-effort: si la miniatura falla, el original ya quedó guardado
            # y `url_publica` de la miniatura simplemente dará 404.
            logger.exception("No se pudo generar la miniatura de %s", key)

    async def eliminar(self, key: str) -> None:
        await run_in_threadpool(media_storage.borrar, key)

    def url_publica(self, key: str, *, expira: int | None = None) -> str:
        return media_storage.url_publica(key)
