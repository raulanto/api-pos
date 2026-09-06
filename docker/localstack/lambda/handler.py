"""Lambda de miniaturas.

Disparada por `s3:ObjectCreated` en el bucket de imágenes, con filtro de prefijo
`originales/`. Por cada objeto:

    originales/<dueno>/<id>/<uuid>.<ext>   ->   thumbnails/<dueno>/<id>/<uuid>.<ext>

Redimensiona a un cuadro de 400x400 (conserva proporción) y sube la miniatura en
el mismo formato. Idempotente: sobrescribe si ya existía.

En LocalStack el endpoint de S3 se alcanza en `http://<LOCALSTACK_HOSTNAME>:4566`
desde dentro del contenedor de la Lambda.
"""
import io
import os
import urllib.parse

import boto3
from PIL import Image

PREFIJO_ORIGINALES = "originales/"
PREFIJO_MINIATURAS = "thumbnails/"
TAMANO_MAX = (400, 400)

# Formato PIL por extensión / content-type.
_FORMATO = {"jpg": "JPEG", "jpeg": "JPEG", "png": "PNG", "webp": "WEBP"}
_CONTENT_TYPE = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}


def _s3():
    endpoint = os.environ.get("AWS_ENDPOINT_URL") or (
        f"http://{os.environ.get('LOCALSTACK_HOSTNAME', 'localhost')}:4566"
    )
    return boto3.client("s3", endpoint_url=endpoint)


def _key_miniatura(key: str) -> str:
    if key.startswith(PREFIJO_ORIGINALES):
        return PREFIJO_MINIATURAS + key[len(PREFIJO_ORIGINALES):]
    return PREFIJO_MINIATURAS + key


def _procesar(s3, bucket: str, key: str) -> None:
    if not key.startswith(PREFIJO_ORIGINALES):
        print(f"[thumbnailer] ignoro (prefijo no es {PREFIJO_ORIGINALES!r}): {key}")
        return

    obj = s3.get_object(Bucket=bucket, Key=key)
    original = obj["Body"].read()

    imagen = Image.open(io.BytesIO(original))
    formato = imagen.format or _FORMATO.get(key.rsplit(".", 1)[-1].lower(), "PNG")
    imagen.thumbnail(TAMANO_MAX)

    buffer = io.BytesIO()
    if formato == "JPEG" and imagen.mode not in ("RGB", "L"):
        imagen = imagen.convert("RGB")
    imagen.save(buffer, format=formato)
    buffer.seek(0)

    destino = _key_miniatura(key)
    s3.put_object(
        Bucket=bucket, Key=destino, Body=buffer.getvalue(),
        ContentType=_CONTENT_TYPE.get(formato, "application/octet-stream"),
    )
    print(f"[thumbnailer] {key} ({len(original)} B) -> {destino} ({buffer.getbuffer().nbytes} B)")


def handler(event, context):
    s3 = _s3()
    procesadas = 0
    for record in event.get("Records", []):
        s3_info = record.get("s3", {})
        bucket = s3_info.get("bucket", {}).get("name")
        raw_key = s3_info.get("object", {}).get("key", "")
        key = urllib.parse.unquote_plus(raw_key)
        if not bucket or not key:
            continue
        try:
            _procesar(s3, bucket, key)
            procesadas += 1
        except Exception as exc:  # noqa: BLE001 - un record malo no debe frenar el resto
            print(f"[thumbnailer] ERROR con {key}: {exc!r}")
    return {"procesadas": procesadas}
