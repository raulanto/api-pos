# Guía: cargar imágenes por archivo (S3) en vez de URL

Los productos y sus presentaciones de venta ya no dependen de una `url` externa:
se sube el **archivo** a un endpoint y la API lo guarda en S3 (LocalStack en
dev), genera una miniatura vía Lambda y devuelve URLs **prefirmadas** listas
para mostrar.

El flujo viejo por URL (`POST .../imagenes` con `{"url": "..."}`) sigue
funcionando para imágenes hospedadas por terceros; esta guía cubre el flujo
nuevo por archivo (`.../imagenes/upload`).

---

## 1. Requisitos previos

```bash
# esquema al día (agrega object_key / content_type a producto_imagen)
uv run alembic upgrade head

# stack con S3 + Lambda (si corrés la API por docker-compose, ya lo hace el entrypoint)
docker compose up -d --build
docker compose exec localstack awslocal s3 ls s3://pos-imagenes
```

Si corrés `uvicorn` a mano, la API usa `S3_ENDPOINT_URL` / `S3_PUBLIC_ENDPOINT_URL`
del `.env` (por defecto `http://localhost:4566`). LocalStack tiene que estar
arriba.

---

## 2. Autenticación y permisos

Todas las rutas requieren `Authorization: Bearer <access_token>`.

| Acción | Permiso |
|---|---|
| Listar galería (`GET`) | `inventario.leer` |
| Subir / editar / borrar imagen | `inventario.editar` |

```bash
TOKEN=$(curl -s localhost:8000/api/v1/usuarios/token \
  -d 'username=admin@example.com&password=DevAdmin123!' \
  | python -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')
```

---

## 3. Endpoints nuevos

| Método | Ruta | Qué hace |
|---|---|---|
| `POST` | `/api/v1/inventario/productos/{producto_id}/imagenes/upload` | Sube un archivo a la galería del producto |
| `POST` | `/api/v1/inventario/productos/{producto_id}/unidades/{unidad_id}/imagenes/upload` | Sube un archivo a la galería de una presentación |
| `GET` | `/api/v1/inventario/productos/{producto_id}/imagenes` | Lista la galería (URLs prefirmadas) |
| `GET` | `/api/v1/inventario/productos/{producto_id}/unidades/{unidad_id}/imagenes` | Lista la galería de la presentación |
| `PATCH` | `/api/v1/inventario/productos/{producto_id}/imagenes/{imagen_id}` | Edita `alt_texto` / `orden` / `es_principal` |
| `DELETE` | `/api/v1/inventario/productos/{producto_id}/imagenes/{imagen_id}` | Borra la fila y el objeto + miniatura de S3 |

(Las variantes `.../unidades/{unidad_id}/imagenes/{imagen_id}` para `PATCH` /
`DELETE` existen igual.)

---

## 4. Subir una imagen de producto

**Body: `multipart/form-data`**

| Campo | Tipo | Req. | Notas |
|---|---|---|---|
| `file` | archivo | sí | `image/jpeg`, `image/png` o `image/webp`; ≤ 5 MiB (`IMAGEN_MAX_BYTES`) |
| `alt_texto` | string | no | máx. 255 |
| `orden` | int | no | ≥ 0, default 0 (posición en el carrusel) |
| `es_principal` | bool | no | default `false`; si `true`, desmarca la portada anterior |

### curl

```bash
PID=<producto_id>
curl -s -X POST "localhost:8000/api/v1/inventario/productos/$PID/imagenes/upload" \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@./foto-frontal.png;type=image/png" \
  -F "alt_texto=Vista frontal" \
  -F "orden=0" \
  -F "es_principal=true"
```

### JavaScript (fetch, navegador)

```js
async function subirImagenProducto(productoId, file, { altTexto, orden = 0, esPrincipal = false } = {}) {
  const fd = new FormData();
  fd.append("file", file);                 // File de un <input type="file">
  if (altTexto) fd.append("alt_texto", altTexto);
  fd.append("orden", String(orden));
  fd.append("es_principal", String(esPrincipal));

  const res = await fetch(
    `/api/v1/inventario/productos/${productoId}/imagenes/upload`,
    { method: "POST", headers: { Authorization: `Bearer ${token}` }, body: fd }
    // NO setear Content-Type: el navegador pone el boundary de multipart solo
  );
  const json = await res.json();
  if (!json.success) throw new Error(json.error.message);
  return json.data;   // ImagenResponse
}
```

### axios

```js
const fd = new FormData();
fd.append("file", file);
fd.append("es_principal", "true");

const { data } = await axios.post(
  `/api/v1/inventario/productos/${productoId}/imagenes/upload`,
  fd,
  { headers: { Authorization: `Bearer ${token}` } } // axios detecta FormData
);
const imagen = data.data;
```

---

## 5. Subir una imagen de una presentación (producto_unidad)

Igual que arriba pero con la ruta de la presentación:

```bash
curl -s -X POST \
  "localhost:8000/api/v1/inventario/productos/$PID/unidades/$UNIDAD_ID/imagenes/upload" \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@./unidad-suelta.webp;type=image/webp"
```

Devuelve `producto_unidad_id` seteado y `producto_id: null`.

---

## 6. Listar la galería

```bash
curl -s "localhost:8000/api/v1/inventario/productos/$PID/imagenes" \
  -H "Authorization: Bearer $TOKEN"
```

Cada elemento trae `url` y `thumbnail_url` **prefirmadas** (para imágenes S3) o la
`url` externa tal cual (para las cargadas por el flujo viejo). Vienen ordenadas
por `orden` y luego por antigüedad.

Las imágenes también aparecen embebidas en el producto:
`GET /api/v1/inventario/productos/{id}?include=imagenes` y la portada en
`imagen_principal` sin necesidad de `include`.

---

## 7. Editar metadata (no reemplaza el archivo)

```bash
curl -s -X PATCH \
  "localhost:8000/api/v1/inventario/productos/$PID/imagenes/$IMG_ID" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"orden": 2, "es_principal": true}'
```

Campos (todos opcionales): `alt_texto`, `cambiar_alt_texto` (para poder ponerlo
en `null`), `orden`, `es_principal`. **No mandes `url`** para una imagen subida a
S3: ese campo es solo para el flujo por URL externa. Para cambiar el archivo,
subí uno nuevo con `upload` y borrá el anterior.

---

## 8. Borrar

```bash
curl -s -X DELETE \
  "localhost:8000/api/v1/inventario/productos/$PID/imagenes/$IMG_ID" \
  -H "Authorization: Bearer $TOKEN" -i     # 204 No Content
```

Borra la fila y, si era una imagen S3, también el original y su miniatura del
bucket.

---

## 9. Formato de respuesta

Sobre estándar de la API:

```json
{
  "success": true,
  "data": {
    "id": "7b3f...","producto_id": "a34a...","producto_unidad_id": null,
    "url":           "http://localhost:4566/pos-imagenes/originales/producto/a34a.../c1d2.png?X-Amz-Algorithm=...",
    "thumbnail_url": "http://localhost:4566/pos-imagenes/thumbnails/producto/a34a.../c1d2.png?X-Amz-Algorithm=...",
    "object_key":    "originales/producto/a34a.../c1d2.png",
    "alt_texto": "Vista frontal",
    "orden": 0,
    "es_principal": true
  }
}
```

| Campo | Para qué sirve |
|---|---|
| `url` | Mostrar la imagen a tamaño completo. Prefirmada, **expira** (`S3_PRESIGN_EXPIRA_SEGUNDOS`, 1 h). Volvé a pedir el `GET` para refrescarla. |
| `thumbnail_url` | Miniatura 400×400 (grillas, carrusel). Puede dar **404 ~1-2 s** después de subir, hasta que la Lambda la genera. |
| `object_key` | Identificador estable del objeto en S3. Guardalo si necesitás referencia; para mostrar usá siempre `url`/`thumbnail_url`. |

---

## 10. Errores

Sobre de error: `{"success": false, "error": {"code": "...", "message": "...", "fields": {...}}}`.

| HTTP | Caso |
|---|---|
| `400` | Tipo de archivo fuera de `image/jpeg\|png\|webp`, archivo vacío, o > 5 MiB |
| `401` | Falta / venció el token |
| `403` | El usuario no tiene `inventario.editar` (o está fuera del alcance de su sucursal) |
| `404` | `producto_id` / `unidad_id` / `imagen_id` inexistente o la presentación no es de ese producto |
| `422` | `orden` negativo, `alt_texto` > 255, `file` ausente |

---

## 11. Migrar del flujo por URL

- **Frontend nuevo**: usar solo `.../imagenes/upload`. El `<input type="file">`
  manda el `File` en `FormData`; no setear `Content-Type` a mano.
- **Datos existentes** con `url` externa: siguen funcionando; `object_key` y
  `thumbnail_url` van `null`. Si querés migrarlos a S3, hay que descargar el
  binario y re-subirlo por `upload` (no hay endpoint que lo haga solo).
- Una fila es **o** URL externa **o** S3, nunca las dos: si subís por `upload`,
  `url` en la BD queda `NULL` y la pública se deriva prefirmada en cada lectura.
