# Imágenes de catálogo: almacenamiento local + miniatura en Python

Las imágenes de `producto_imagen` pueden vivir como archivo propio en disco (en
vez de depender de una `url` externa). Al subir un archivo, la propia API
genera **en el momento** una miniatura con Pillow — no hay object storage ni
Lambda de por medio.

## Flujo

```
POST /api/v1/inventario/productos/{id}/imagenes/upload   (multipart: file)
        │
        ▼
  FastAPI  ── guarda en disco ──►  media/originales/producto/{id}/{uuid}.png
        │                                   │
        │ guarda object_key en              │  Pillow (mismo request, 400x400)
        │ producto_imagen                   ▼
        │                            media/thumbnails/producto/{id}/{uuid}.png
        ▼
GET .../imagenes  ──►  url y thumbnail_url = /media/... (servidas por la API)
```

- `settings.media_root` (una sola carpeta, dos prefijos): `originales/` y
  `thumbnails/`. Servida como estático por FastAPI en `settings.media_base_url`
  (`/media` por defecto, ver `app/main.py`).
- En BD sólo se guarda `object_key` (+ `content_type`). La key de la miniatura
  se **deriva** (`originales/… → thumbnails/…`), no se persiste.
- `url` de `producto_imagen` sigue existiendo para imágenes por URL externa
  (endpoint JSON `POST .../imagenes` de siempre). Una fila tiene `url` **o**
  `object_key`, nunca las dos.

## Componentes

| Pieza | Ubicación |
|---|---|
| Helper de filesystem (guardar/borrar/url) | `app/core/media_storage.py` |
| Puerto `AlmacenImagenes` | `app/modules/inventario/application/ports/almacen_imagenes.py` |
| Adapter local (guarda + genera miniatura con Pillow) | `app/modules/inventario/infrastructure/adapters/local_almacen_imagenes.py` |
| Caso de uso de subida | `app/modules/inventario/application/use_cases/subir_imagen.py` |
| Endpoints `/upload` | `app/modules/inventario/infrastructure/api/router/imagenes.py` |
| Mount de estáticos | `app/main.py` |
| Migración (`object_key`, `content_type`, `url` nullable) | `alembic/versions/b3d4e5f6a7c8_producto_imagen_s3.py` |

La fachada de sucursal reusa el mismo helper con su propio prefijo
(`app/modules/sucursales/infrastructure/storage/fachada_storage.py`), sin
generar miniatura.

## Levantar

No requiere infra aparte: `docker compose up -d` (o correr `uvicorn` local)
alcanza. La carpeta `media/` se crea sola al arrancar la API y persiste porque
vive bajo el bind-mount `.:/app` de `docker-compose.yml` (está en
`.gitignore`).

## Verificación end-to-end

```bash
TOKEN=$(curl -s localhost:8000/api/v1/usuarios/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"DevAdmin123!"}' \
  | python -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')

PID=<producto_id>
curl -s -X POST "localhost:8000/api/v1/inventario/productos/$PID/imagenes/upload" \
  -H "Authorization: Bearer $TOKEN" \
  -F file=@sample.png -F es_principal=true | tee /tmp/img.json

# url y thumbnail_url ya están listas en la misma respuesta (sin espera).

IMG=$(python -c 'import json;print(json.load(open("/tmp/img.json"))["data"]["id"])')
curl -s -X DELETE "localhost:8000/api/v1/inventario/productos/$PID/imagenes/$IMG" \
  -H "Authorization: Bearer $TOKEN" -i     # borra fila + original + miniatura en disco
```

## Notas

- `SubirImagenUseCase` valida `content_type` (`image/jpeg|png|webp`) y tamaño
  (`IMAGEN_MAX_BYTES`, 5 MiB por defecto) → `ImagenInvalida` (HTTP 400).
- Si falla el `INSERT`/commit tras guardar el archivo, el use case lo borra
  (compensación best-effort).
- La miniatura se genera **de forma síncrona** en el mismo request de subida:
  no hay ventana en la que `thumbnail_url` dé 404.
