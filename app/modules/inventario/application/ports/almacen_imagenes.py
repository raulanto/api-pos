"""Puerto de almacenamiento de archivos de imagen (S3 / compatible).

El módulo `inventario` sube el binario de una imagen a un object storage y sólo
persiste su *object key* en `producto_imagen`. La URL que consume el front se
deriva al leer (`url_publica`, prefirmada). La miniatura la genera fuera de
banda una Lambda disparada por el evento `s3:ObjectCreated`; su key se deriva
de la original con `key_miniatura` (no se guarda en BD).

Layout de keys en el bucket:
    originales/<dueno>/<dueno_id>/<uuid><ext>   <- dispara la Lambda
    thumbnails/<dueno>/<dueno_id>/<uuid><ext>   <- salida de la Lambda
"""
from abc import ABC, abstractmethod
from uuid import UUID

# content-type -> extensión de archivo. También hace de allowlist.
EXTENSIONES_PERMITIDAS: dict[str, str] = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}

PREFIJO_ORIGINALES = "originales/"
PREFIJO_MINIATURAS = "thumbnails/"


class AlmacenImagenes(ABC):
    @abstractmethod
    async def subir(self, contenido: bytes, content_type: str, key: str) -> None:
        """Sube (o sobrescribe) el objeto `key` con `contenido`."""
        ...

    @abstractmethod
    async def eliminar(self, key: str) -> None:
        """Borra el objeto `key`. Best-effort: no falla si no existe."""
        ...

    @abstractmethod
    def url_publica(self, key: str, *, expira: int | None = None) -> str:
        """URL `GET` prefirmada para que el navegador descargue el objeto."""
        ...

    def nueva_key(self, *, dueno: str, dueno_id: UUID, content_type: str) -> str:
        """Genera la key de un original nuevo. `dueno` es 'producto' o 'unidad'."""
        from uuid import uuid4

        ext = EXTENSIONES_PERMITIDAS[content_type]
        return f"{PREFIJO_ORIGINALES}{dueno}/{dueno_id}/{uuid4().hex}{ext}"

    @staticmethod
    def key_miniatura(key_original: str) -> str:
        """`originales/a/b.jpg` -> `thumbnails/a/b.jpg`."""
        if key_original.startswith(PREFIJO_ORIGINALES):
            return PREFIJO_MINIATURAS + key_original[len(PREFIJO_ORIGINALES):]
        return PREFIJO_MINIATURAS + key_original
