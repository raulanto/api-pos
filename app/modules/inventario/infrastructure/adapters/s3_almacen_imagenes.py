"""Adapter S3 (boto3) del puerto `AlmacenImagenes`.

boto3 es síncrono: cada llamada de red se corre en el threadpool de Starlette
para no bloquear el event loop. El presign es local (no hace I/O), así que
`url_publica` queda síncrono.
"""
import logging

from botocore.exceptions import ClientError
from fastapi.concurrency import run_in_threadpool

from app.core.aws import get_s3_client, presign_get_url
from app.core.config import settings
from app.modules.inventario.application.ports.almacen_imagenes import AlmacenImagenes

logger = logging.getLogger(__name__)


class S3AlmacenImagenes(AlmacenImagenes):
    def __init__(self) -> None:
        self._bucket = settings.s3_bucket_imagenes

    async def subir(self, contenido: bytes, content_type: str, key: str) -> None:
        await run_in_threadpool(
            get_s3_client().put_object,
            Bucket=self._bucket,
            Key=key,
            Body=contenido,
            ContentType=content_type,
        )

    async def eliminar(self, key: str) -> None:
        try:
            await run_in_threadpool(
                get_s3_client().delete_object, Bucket=self._bucket, Key=key
            )
        except ClientError as exc:  # noqa: BLE001 - best-effort, no debe tumbar el request
            logger.warning("No se pudo borrar %s de S3: %s", key, exc)

    def url_publica(self, key: str, *, expira: int | None = None) -> str:
        return presign_get_url(key, expira=expira)
