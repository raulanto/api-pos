# Guía: cargar imágenes por archivo (disco local) en vez de URL

Los productos y sus presentaciones de venta ya no dependen de una `url` externa:
se sube el **archivo** a un endpoint, la API lo guarda en disco y genera al
mismo tiempo una miniatura (Pillow), devolviendo URLs listas para mostrar.

El flujo viejo por URL (`POST .../imagenes` con `{"url": "..."}`) sigue
funcionando para imágenes hospedadas por terceros; esta guía cubre el flujo
nuevo por archivo (`.../imagenes/upload`).

---

## 1. Requisitos previos

```bash
# esquema al día (agrega object_key / content_type a producto_imagen)
uv run alembic upgrade head
```

No hace falta infra aparte: la API guarda los archivos bajo `MEDIA_ROOT`
(`media/` por defecto) y los sirve ella misma en `MEDIA_BASE_URL` (`/media`).

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
| `DELETE` | `/api/v1/inventario/productos/{producto_id}/imagenes/{imagen_id}` | Borra la fila y el archivo + miniatura en disco |

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

Cada elemento trae `url` y `thumbnail_url` resueltas (para imágenes propias) o la
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
en `null`), `orden`, `es_principal`. **No mandes `url`** para una imagen propia:
ese campo es solo para el flujo por URL externa. Para cambiar el archivo, subí
uno nuevo con `upload` y borrá el anterior.

---

## 8. Borrar

```bash
curl -s -X DELETE \
  "localhost:8000/api/v1/inventario/productos/$PID/imagenes/$IMG_ID" \
  -H "Authorization: Bearer $TOKEN" -i     # 204 No Content
```

Borra la fila y, si era una imagen propia, también el original y su miniatura
en disco.

---

## 9. Formato de respuesta

Sobre estándar de la API:

```json
{
  "success": true,
  "data": {
    "id": "7b3f...","producto_id": "a34a...","producto_unidad_id": null,
    "url":           "/media/originales/producto/a34a.../c1d2.png",
    "thumbnail_url": "/media/thumbnails/producto/a34a.../c1d2.png",
    "object_key":    "originales/producto/a34a.../c1d2.png",
    "alt_texto": "Vista frontal",
    "orden": 0,
    "es_principal": true
  }
}
```

| Campo | Para qué sirve |
|---|---|
| `url` | Mostrar la imagen a tamaño completo. No expira; se sirve directo desde la API. |
| `thumbnail_url` | Miniatura 400×400 (grillas, carrusel). Ya está lista en la misma respuesta del `upload` (se genera en el mismo request, no hay espera). |
| `object_key` | Identificador estable del archivo. Guardalo si necesitás referencia; para mostrar usá siempre `url`/`thumbnail_url`. |

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
  `thumbnail_url` van `null`. Si querés migrarlos al almacén propio, hay que
  descargar el binario y re-subirlo por `upload` (no hay endpoint que lo haga solo).
- Una fila es **o** URL externa **o** propia, nunca las dos: si subís por
  `upload`, `url` en la BD queda `NULL` y la pública se deriva en cada lectura.
