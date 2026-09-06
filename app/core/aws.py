"""Clientes boto3 para S3.

Dos clientes, misma credencial/región, distinto endpoint:

- `get_s3_client()`      -> `s3_endpoint_url`.  I/O real (subir, borrar, leer).
  Dentro de docker-compose esto resuelve a `http://localstack:4566`.
- `get_s3_public_client()` -> `s3_public_endpoint_url`.  SÓLO para firmar URLs
  `GET` que abrirá el navegador: tiene que apuntar a un host alcanzable desde
  afuera (`http://localhost:4566`), no al nombre interno de la red de compose.

Con ambos endpoints en None se usa AWS real (endpoint por defecto de boto3).
Los clientes se cachean: boto3 los hace thread-safe una vez creados.
"""
from functools import lru_cache

import boto3
from botocore.client import BaseClient
from botocore.config import Config

from app.core.config import settings

# Path-style addressing: LocalStack no resuelve el virtual-host
# `bucket.s3.amazonaws.com`, necesita `.../s3/bucket/key`.
_S3_CONFIG = Config(signature_version="s3v4", s3={"addressing_style": "path"})


def _build_s3(endpoint_url: str | None) -> BaseClient:
    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        region_name=settings.s3_region,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
        config=_S3_CONFIG,
    )


@lru_cache(maxsize=1)
def get_s3_client() -> BaseClient:
    """Cliente para operaciones de I/O (endpoint interno)."""
    return _build_s3(settings.s3_endpoint_url)


@lru_cache(maxsize=1)
def get_s3_public_client() -> BaseClient:
    """Cliente para firmar URLs GET destinadas al navegador (endpoint público)."""
    return _build_s3(settings.s3_public_endpoint_url or settings.s3_endpoint_url)


def presign_get_url(key: str, *, expira: int | None = None) -> str:
    """URL `GET` prefirmada del objeto `key` en el bucket de imágenes.

    Es cómputo local (firma), sin I/O: seguro de llamar en caliente y en bucle.
    """
    return get_s3_public_client().generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.s3_bucket_imagenes, "Key": key},
        ExpiresIn=expira or settings.s3_presign_expira_segundos,
    )
