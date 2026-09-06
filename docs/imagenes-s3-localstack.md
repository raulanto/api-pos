# Imágenes de catálogo en S3 + Lambda de miniaturas (LocalStack)

Las imágenes de `producto_imagen` pueden vivir en un bucket S3 propio (emulado
con **LocalStack** en desarrollo) en vez de depender de una URL externa. Al
subir un archivo, una **AWS Lambda** disparada por el evento `s3:ObjectCreated`
genera automáticamente una miniatura.

## Flujo

```
POST /api/v1/inventario/productos/{id}/imagenes/upload   (multipart: file)
        │
        ▼
  FastAPI  ── boto3 put_object ──►  S3  s3://pos-imagenes/originales/producto/{id}/{uuid}.png
        │                                   │
        │ guarda object_key en              │  evento s3:ObjectCreated (prefijo originales/)
        │ producto_imagen                   ▼
        │                            Lambda pos-thumbnailer  (Pillow, 400x400)
        │                                   │
        │                                   ▼
        │                          S3  s3://pos-imagenes/thumbnails/producto/{id}/{uuid}.png
        ▼
GET .../imagenes  ──►  url y thumbnail_url PREFIRMADAS (http://localhost:4566/...)
```

- Bucket único `pos-imagenes`, dos prefijos: `originales/` (dispara la Lambda) y
  `thumbnails/` (salida; no dispara, evita recursión).
- En BD sólo se guarda `object_key` (+ `content_type`). La key de la miniatura se
  **deriva** (`originales/… → thumbnails/…`), no se persiste.
- `url` de `producto_imagen` sigue existiendo para imágenes por URL externa
  (endpoint JSON `POST .../imagenes` de siempre). Una fila tiene `url` **o**
  `object_key`, nunca las dos.

## Componentes

| Pieza | Ubicación |
|---|---|
| Servicios `localstack`, `lambda_build` | `docker-compose.yml` |
| Handler de la Lambda | `docker/localstack/lambda/handler.py` |
| Bootstrap (bucket + deploy + trigger) | `docker/localstack/init/ready.d/10-init.sh` |
| Clientes boto3 (interno + público) | `app/core/aws.py` |
| Puerto `AlmacenImagenes` | `app/modules/inventario/application/ports/almacen_imagenes.py` |
| Adapter S3 | `app/modules/inventario/infrastructure/adapters/s3_almacen_imagenes.py` |
| Caso de uso de subida | `app/modules/inventario/application/use_cases/subir_imagen.py` |
| Endpoints `/upload` | `app/modules/inventario/infrastructure/api/router/imagenes.py` |
| Migración (`object_key`, `content_type`, `url` nullable) | `alembic/versions/b3d4e5f6a7c8_producto_imagen_s3.py` |

## Levantar

```bash
docker compose up -d --build
# espera: lambda_build termina con exit 0, y `localstack` queda healthy
docker compose ps
```

> La primera invocación de la Lambda hace que LocalStack descargue la imagen
> `public.ecr.aws/lambda/python:3.12` (necesita internet una vez). En hosts
> **arm64** ajustar el wheel de Pillow del servicio `lambda_build`.

## Verificación end-to-end

```bash
# 1. Infra lista
docker compose exec localstack awslocal s3 ls s3://pos-imagenes
docker compose exec localstack awslocal lambda list-functions
docker compose exec localstack awslocal s3api get-bucket-notification-configuration --bucket pos-imagenes

# 2. Token
TOKEN=$(curl -s localhost:8000/api/v1/usuarios/token \
  -d 'username=admin@example.com&password=DevAdmin123!' | python -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')

# 3. Subir una imagen a un producto existente
PID=<producto_id>
curl -s -X POST "localhost:8000/api/v1/inventario/productos/$PID/imagenes/upload" \
  -H "Authorization: Bearer $TOKEN" \
  -F file=@sample.png -F es_principal=true | tee /tmp/img.json

# 4. Abrir la `url` devuelta (presigned) en el navegador -> carga la imagen

# 5. Confirmar original y miniatura en S3
docker compose exec localstack awslocal s3 ls s3://pos-imagenes/originales/ --recursive
docker compose exec localstack awslocal s3 ls s3://pos-imagenes/thumbnails/ --recursive   # ~1-2 s después
docker compose logs localstack | grep -i thumbnailer

# 6. Listar la galería (trae url + thumbnail_url prefirmadas)
curl -s "localhost:8000/api/v1/inventario/productos/$PID/imagenes" -H "Authorization: Bearer $TOKEN"

# 7. Borrar: quita la fila y también el original + miniatura de S3
IMG=$(python -c 'import json;print(json.load(open("/tmp/img.json"))["data"]["id"])')
curl -s -X DELETE "localhost:8000/api/v1/inventario/productos/$PID/imagenes/$IMG" -H "Authorization: Bearer $TOKEN" -i
```

## Notas

- `SubirImagenUseCase` valida `content_type` (`image/jpeg|png|webp`) y tamaño
  (`IMAGEN_MAX_BYTES`, 5 MiB por defecto) → `ImagenInvalida` (HTTP 400).
- Si falla el `INSERT`/commit tras subir a S3, el use case borra el objeto
  recién subido (compensación best-effort).
- `thumbnail_url` prefirma una key que puede dar **404 unos segundos** hasta que
  la Lambda termina.
