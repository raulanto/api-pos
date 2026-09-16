"""Almacenamiento local de imágenes (filesystem), sin S3/LocalStack.

Los binarios se guardan bajo `settings.media_root` con la misma jerarquía de
`key` que antes usaba el bucket (`originales/<dueno>/<id>/<uuid><ext>`). Se
sirven como estático en `settings.media_base_url` (mount en `app/main.py`).
"""
import logging
from pathlib import Path

from app.core.config import settings

logger = logging.getLogger(__name__)


def _ruta(key: str) -> Path:
    return Path(settings.media_root) / key


def guardar(key: str, contenido: bytes) -> None:
    ruta = _ruta(key)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_bytes(contenido)


def borrar(key: str) -> None:
    """Best-effort: no falla si el archivo no existe."""
    try:
        _ruta(key).unlink()
    except FileNotFoundError:
        pass
    except OSError as exc:
        logger.warning("No se pudo borrar %s: %s", key, exc)


def url_publica(key: str) -> str:
    return f"{settings.media_base_url.rstrip('/')}/{key}"
