"""Storage de la imagen de fachada de una sucursal.

Reusa la capa S3 del proyecto (`app/core/aws.py`) sin abstracción nueva. Mismo
bucket que las imágenes de producto (`settings.s3_bucket_imagenes`), prefijo
`sucursales/`. La Lambda de miniaturas de inventario filtra por prefijo
`originales/`, así que no se dispara con las fachadas.
"""
import logging
from uuid import UUID, uuid4

from botocore.exceptions import ClientError
from fastapi.concurrency import run_in_threadpool

from app.core.aws import get_s3_client, presign_get_url
from app.core.config import settings

logger = logging.getLogger(__name__)

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
    await run_in_threadpool(
        get_s3_client().put_object,
        Bucket=settings.s3_bucket_imagenes,
        Key=key,
        Body=contenido,
        ContentType=content_type,
    )


async def eliminar(key: str) -> None:
    try:
        await run_in_threadpool(
            get_s3_client().delete_object,
            Bucket=settings.s3_bucket_imagenes,
            Key=key,
        )
    except ClientError as exc:  # noqa: BLE001 - best-effort
        logger.warning("No se pudo borrar %s de S3: %s", key, exc)


def url_publica(key: str) -> str:
    return presign_get_url(key)
