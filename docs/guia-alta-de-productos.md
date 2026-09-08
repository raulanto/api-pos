# Guía para dar de alta un producto (para la app)

> Pensada para quien construye la pantalla de "Nuevo producto" en la app.
> Lenguaje simple, con los llamados a la API que hay que hacer y en qué orden.
> Todos los endpoints cuelgan de `/api/v1/inventario`.

---

## La idea en dos minutos

Un **producto** es cualquier cosa que la tienda vende o guarda en inventario.
Antes de venderlo hay que:

1. decir **qué tipo de cosa es** (normal, por peso/volumen, un combo, o un servicio),
2. **crearlo** con su precio y su costo,
3. (opcional) agregarle **formas de venta** distintas (la lata suelta y la reja),
4. (opcional) agregarle **fotos**,
5. **cargarle stock inicial** en cada sucursal donde se va a vender.

El stock siempre se guarda en **una sola unidad** (la "unidad base" del producto).
Todo lo demás —rejas, cajas, six-packs— son sólo formas de vender esa misma unidad.

Los **descuentos y 2x1** (y el mayoreo de una presentación puntual) no se cargan
en el producto: van en el módulo de **Promociones**, que apunta a productos o
presentaciones. Sección "Promociones" más abajo.

---

## Los 4 tipos de producto (en palabras)

| Tipo | Cuándo usarlo | Ejemplo |
|------|---------------|---------|
| **simple** | Se vende de a piezas enteras. Es el 90% de los casos. | Una camisa, un shampoo, una lata de refresco |
| **fraccionable** | Se vende en pedazos: por kilo, por litro, por metro. | Jamón por kg, aceite a granel, tela por metro |
| **kit** | Es un combo armado con otros productos. No tiene stock propio: al venderlo se descuenta de sus partes. | "Combo desayuno" = café + medialuna |
| **servicio** | No es una cosa física, no mueve inventario. | Flete, instalación, mano de obra |

Si dudás entre `simple` y `fraccionable`: ¿el cliente puede pedir "medio"? Si sí,
es `fraccionable`.

---

## Paso a paso

### Paso 1 — Elegir la categoría

El producto necesita una categoría. La pantalla debería mostrar un desplegable
que se llena con:

```
GET /categorias
```

Si la tienda todavía no cargó categorías, se crean con `POST /categorias`
(`{ "nombre": "Bebidas" }`).

### Paso 2 — Elegir la unidad de medida

Es "¿en qué se mide este producto?": pieza, kilo, litro, metro, reja…
El desplegable se llena con:

```
GET /unidades-medida
```

Vienen ya cargadas las comunes (`unidad`, `pza`, `kg`, `g`, `l`, `ml`, `m`,
`reja`, `caja`…). Cada una trae un campo **`decimales`**: cuántos decimales
tiene sentido para esa unidad (0 para piezas, 3 para kilos). La app puede usar
ese número para limitar el input de cantidades.

Si falta una unidad, se crea con:

```
POST /unidades-medida
{
  "codigo": "rollo",
  "nombre": "Rollo",
  "tipo_magnitud": "conteo",     // conteo | masa | volumen | longitud | tiempo
  "decimales": 0
}
```

> La unidad de medida **no es obligatoria** para crear el producto (hay un campo
> de texto libre como respaldo), pero conviene siempre elegir una del catálogo:
> así el sistema sabe cuántos decimales aceptar y los reportes salen prolijos.

### Paso 3 — Crear el producto

```
POST /productos
```

Campos del formulario:

| Campo | ¿Obligatorio? | Qué es |
|-------|---------------|--------|
| `nombre` | sí | Nombre visible |
| `sku` | sí | Código interno único (lo pone la tienda). Si el producto se da de baja, el SKU queda libre para reusar |
| `categoria_id` | sí | Del Paso 1 |
| `unidad_medida` | sí | Texto ("pieza", "kilo"). Poné el `nombre` de la unidad elegida |
| `unidad_medida_id` | recomendado | El `id` de la unidad del Paso 2 |
| `precio_venta` | sí | Precio al público de **1 unidad base** |
| `costo` | sí | Lo que le cuesta a la tienda |
| `impuesto_tasa` | sí | % de impuesto (0 si no aplica) |
| `tipo` | no (por defecto `simple`) | Uno de los 4 tipos |
| `codigo_barras` | no | El de la unidad base. También único entre activos |
| `descripcion` | no | Texto largo |
| `permite_stock_negativo` | no (por defecto `false`) | Si se permite vender aunque el stock quede en negativo |
| `requiere_lote` | no (por defecto `false`) | Si el producto se controla por lote: cada carga de stock pide un lote (código + caducidad) y las ventas descuentan del que vence primero. Ver la sección "Productos con lote". No se puede activar si ya tiene stock cargado |
| `permite_venta_fraccionada` | no | Si se puede vender "medio". Con `tipo: "fraccionable"` se activa solo |
| `incremento_minimo_venta` | no | Si se define, toda venta debe ser múltiplo de este número (ej: `0.25` kg, `50` ml) |
| `precio_incluye_impuesto` | no (por defecto `false`) | `precio_venta` ya trae el IVA adentro (precio final al público). Es informativo para el front/reportes: el sistema no recalcula impuesto en la venta |
| `precio_mayoreo` + `cantidad_minima_mayoreo` | no (van juntos) | Precio de **mayoreo**: al vender por unidad base una cantidad ≥ el mínimo, el sistema usa este precio en vez de `precio_venta` (menudeo). Ver "Mayoreo y sobre pedido" |
| `es_sobre_pedido` | no (por defecto `false`) | El producto no se stockea: se puede vender sin existencia (como `permite_stock_negativo`) |
| `monedero_pct` / `monedero_monto` | no | **Monedero** (cashback): al vender este producto con un `telefono`, la línea genera saldo de monedero. `monedero_pct` = % del subtotal (0–100); si no, `monedero_monto` = fijo por unidad. Nulos = no genera. La presentación lo puede sobreescribir. Ver `docs/guia-ventas-y-caja.md` §2.12 |
| `rastrea_instancia_abierta` + `instancia_capacidad_default` | no | Rastrear cada **envase abierto** vendido en fracciones (aceite a granel, químicos). `instancia_capacidad_default` (> 0) es obligatorio si se activa. Flujo aparte: `docs/instancia-fisica-abierta.md` |

**Ejemplo — producto normal (una lata de refresco):**

```json
{
  "sku": "REF-COLA-355",
  "nombre": "Refresco Cola 355ml",
  "categoria_id": "…",
  "unidad_medida": "pieza",
  "unidad_medida_id": "…",
  "precio_venta": 18,
  "costo": 11,
  "impuesto_tasa": 16,
  "codigo_barras": "7501234567890"
}
```

**Ejemplo — producto por peso (jamón):**

```json
{
  "sku": "EMB-JAMON",
  "nombre": "Jamón cocido",
  "categoria_id": "…",
  "unidad_medida": "kilo",
  "unidad_medida_id": "…",
  "precio_venta": 320,
  "costo": 210,
  "impuesto_tasa": 0,
  "tipo": "fraccionable",
  "incremento_minimo_venta": 0.05
}
```
Precio por **kilo**. Con `incremento_minimo_venta: 0.05` la app sólo deja vender
50 g, 100 g, 150 g… y una venta de 0.03 kg es rechazada.

**Ejemplo — servicio:**

```json
{
  "sku": "SERV-FLETE",
  "nombre": "Flete a domicilio",
  "categoria_id": "…",
  "unidad_medida": "servicio",
  "precio_venta": 150,
  "costo": 0,
  "impuesto_tasa": 0,
  "tipo": "servicio"
}
```
No pide stock, no aparece en inventario. Se puede vender siempre.

La respuesta trae el `id` del producto nuevo. Guárdalo para los pasos siguientes.

### Paso 3b — Mayoreo y "sobre pedido" (opcional)

**Mayoreo.** Si el producto tiene un precio distinto por volumen, mandá los dos
campos juntos:

```json
{
  "…": "…",
  "precio_venta": 18,
  "precio_mayoreo": 15,
  "cantidad_minima_mayoreo": 12
}
```

Al vender **por unidad base** (no por presentación) una cantidad de 12 o más, el
sistema cobra `precio_mayoreo` — lo aplica solo y lo congela en la venta, aunque
el POS haya mandado otro precio. Menos de 12 → `precio_venta` normal. Las
presentaciones (la reja) siguen con su propio precio.

Este `precio_mayoreo` es el **mayoreo simple, sólo para la unidad base**. Para
2x1 / 3x2, un % de descuento, mayoreo **de una presentación concreta** (la reja),
o promociones con fecha de inicio y fin, se usa el módulo de **Promociones**
(sección más abajo). Los dos pueden convivir: el `precio_mayoreo` fija el precio
y la promoción se calcula encima.

**Sobre pedido.** `"es_sobre_pedido": true` para lo que no se guarda en stock y se
encarga al proveedor cuando alguien lo compra. Se puede vender aunque la
existencia esté en 0.

**Precio con IVA incluido.** `"precio_incluye_impuesto": true` avisa que
`precio_venta` ya es el precio final. El sistema **no** recalcula impuestos en la
venta (el total es cantidad × precio − descuento); la bandera es para que tu app
sepa si mostrar "IVA incluido" o desglosarlo.

### Paso 4 — Formas de venta adicionales (opcional)

Sólo si el producto se vende en **más de un formato**. Ejemplo: la lata suelta
**y** la reja de 24.

Primero elegís cuál es la unidad base (la más chica, normalmente): la lata.
Eso es lo que ya creaste en el Paso 3. La reja se agrega como "presentación":

```
POST /productos/{id}/unidades
{
  "nombre": "Reja x24",
  "unidad_medida": "reja",
  "precio_venta": 380,
  "factor": 24            // cuántas unidades base entran en 1 reja
}
```

Si te resulta más natural pensarlo al revés ("¿cuántas de estas entran en 1
unidad base?"), mandás `unidades_por_base` en lugar de `factor`. Ejemplo: una
reja tiene 6 refrescos grandes → `"unidades_por_base": 6`.

Cada presentación puede tener su **propio código de barras** (`codigo_barras`),
así el escáner del POS la reconoce sola. También su propio **monedero**
(`monedero_pct` / `monedero_monto`): si mandás alguno de los dos, esa
presentación usa esa config en vez de la del producto para el cashback.

**Editar / dar de baja / reactivar una presentación:**

- `PATCH /productos/{id}/unidades/{unidad_id}` — cambia nombre, factor, precio o código.
  Para fijar/limpiar el monedero de la presentación: `cambiar_monedero: true`
  (con o sin `monedero_pct` / `monedero_monto`; si no vienen, se limpian).
- `DELETE /productos/{id}/unidades/{unidad_id}` — baja **lógica** (`activo = false`);
  las ventas históricas siguen apuntando a ella.
- `PATCH /productos/{id}/unidades/{unidad_id}/reactivar` — la vuelve a activar.
  Falla con 409 si otra presentación **activa** del mismo producto ya usa ese
  `nombre` o `codigo_barras` (renombrá o desactivá esa primero).
- `GET /productos/{id}/unidades?incluir_inactivas=true` para listar también las dadas de baja.

> Los `kit` **no** llevan presentaciones (su "receta" se arma con
> `PUT /productos/{id}/componentes`). Eso es otro flujo.

### Paso 5 — Fotos (opcional)

Dos formas:

**A) Subir el archivo a la API** (recomendado). `multipart/form-data`, el archivo
en el campo `file`:

```
POST /productos/{id}/imagenes/upload
  file=<jpg/png/webp, ≤ 5 MB>
  alt_texto=Refresco cola lata 355ml
  orden=0
  es_principal=true
```

La API lo guarda en su almacén (S3) y responde con `url` y `thumbnail_url` ya
firmadas y listas para mostrar. La miniatura puede tardar 1–2 s en generarse.

**B) Registrar una URL externa** (si ya subiste la foto a tu propio CDN):

```
POST /productos/{id}/imagenes
{
  "url": "https://tu-cdn.com/productos/ref-cola.jpg",
  "alt_texto": "Refresco cola lata 355ml",
  "orden": 0,
  "es_principal": true
}
```

- `orden`: para el carrusel (0 = primera).
- `es_principal`: la portada. Sólo puede haber **una**: si marcás otra como
  principal, la anterior se desmarca sola.
- `DELETE /productos/{id}/imagenes/{imagen_id}` borra la imagen (y su archivo en
  S3 si la habías subido por la opción A).

La foto de portada aparece en `imagen_principal` cada vez que pedís el producto
(en el detalle y en el listado), sin necesidad de pedir nada extra.

Las presentaciones (la reja) también pueden tener sus propias fotos:
`POST /productos/{id}/unidades/{unidad_id}/imagenes` (o `.../imagenes/upload`).
Su portada viaja en `unidades[].imagen_principal` cuando pedís
`GET /productos?include=unidades` (mismo formato que la del producto: `url` y
`thumbnail_url` prefirmadas si vive en S3), para que el POS pinte cada
presentación con su miniatura.

### Paso 6 — Cargar el stock inicial

El producto ya existe pero tiene **0** en todas las sucursales. Para cada
sucursal donde se va a vender:

```
POST /movimientos
{
  "producto_id": "…",
  "sucursal_id": "…",
  "tipo": "entrada",
  "cantidad": 120,             // en unidad base (120 latas)
  "referencia_tipo": "compra",
  "costo_unitario": 11,
  "stock_minimo": 24           // umbral de alerta (sólo se toma en la 1ª carga)
}
```

- `cantidad` va **siempre en unidad base** (latas, kilos, metros), aunque hayas
  comprado "5 rejas": convertí a 120 en la app, o mandá también
  `unidad_capturada_id` + `cantidad_capturada` para dejar registro de que se
  cargó "5 rejas".
- `stock_minimo` (y `stock_maximo`) se fijan acá la primera vez. Después se
  cambian con `PATCH /existencias/{producto_id}/{sucursal_id}/umbrales`.
- Si además querés que esta compra **actualice el costo del producto**, agregá
  `"actualizar_costo": true`. Para actualizar también el precio de venta,
  `"nuevo_precio_venta": 19`.

Servicios y kits **no** necesitan este paso.

---

## Productos con lote (medicamentos, lácteos, perecederos)

Si al crear el producto pusiste `"requiere_lote": true`, el manejo de stock
cambia un poco:

**Al cargar stock**, cada `POST /movimientos` tipo `entrada` tiene que decir a
qué lote entra. Lo normal es crearlo en el momento:

```
POST /movimientos
{
  "producto_id": "…", "sucursal_id": "…", "tipo": "entrada",
  "cantidad": 50, "referencia_tipo": "compra",
  "lote_nuevo": {
    "codigo_lote": "L-2026-0473",
    "fecha_caducidad": "2026-12-31",
    "costo": 18.50
  }
}
```

Si el lote ya existe (otra compra del mismo), mandás `"lote_id": "<id>"` en vez de
`lote_nuevo`. También podés crear lotes por adelantado con
`POST /productos/{id}/lotes`.

**Al vender** no hay que hacer nada especial: el sistema descuenta
automáticamente del lote que **vence primero** (FEFO). Si una venta no entra en un
solo lote, se reparte entre varios.

**Panel de caducidades**: `GET /lotes/por-vencer?dias=30` te da los lotes que
vencen en los próximos 30 días (y los ya vencidos) con su saldo por sucursal.

**Ajustes / recuento**: `POST /movimientos` tipo `ajuste` sobre un producto con
lote necesita `"lote_id"`; el `cantidad_final` es el saldo objetivo **de ese
lote**.

**Ojo**:

- No se puede activar `requiere_lote` en un producto que ya tiene stock. Primero
  llevá el stock a 0.
- La transferencia entre sucursales sí funciona: saca por FEFO en origen y entra
  al mismo lote en destino. Sólo se permite entre una sucursal y su sucursal
  padre directa, o entre sucursales hermanas.

---

## Promociones y descuentos

Las promociones (2x1, %, precio fijo, mayoreo por presentación), los **cupones**
y el **descuento manual** del POS viven en su propio módulo y tienen guía aparte:
**`docs/guia-promociones.md`**.

En resumen: son una capa sobre el producto, se configuran en `/api/v1/promociones`
(permisos `promociones.crear|editar|leer`), pueden apuntar a un `producto_id`, a
un `producto_unidad_id` (presentación) o a una `categoria_id`, y el backend las
aplica solo al vender —el POS no manda nada—. No tocan el stock ni cambian el
producto.

---

## Casos completos de ejemplo

### A) Abarrote común

1. `POST /productos` (`tipo` omitido → `simple`)
2. `POST /productos/{id}/imagenes` (portada)
3. `POST /movimientos` `entrada` por sucursal

### B) Bebida que se vende por lata y por reja

1. `POST /productos` — unidad base = **lata**
2. `POST /productos/{id}/unidades` — "Reja x24", `factor: 24`, con su código de barras
3. `POST /productos/{id}/imagenes`
4. `POST /movimientos` `entrada` — cantidad en **latas**

Al vender, el POS escanea el código: si es el de la lata, descuenta 1; si es el
de la reja, descuenta 24. Todo del mismo saldo.

### C) Producto por kilo

1. `POST /productos` — `tipo: "fraccionable"`, `unidad_medida_id` = kilo,
   `incremento_minimo_venta: 0.05`
2. `POST /movimientos` `entrada` — `cantidad: 8.5` (8 kg y medio)

La app limita el input a múltiplos de 50 g.

### D) Combo (kit)

1. `POST /productos` — `tipo: "kit"`
2. `PUT /productos/{id}/componentes`
   ```json
   { "componentes": [
       { "producto_componente_id": "<café>", "cantidad": 1 },
       { "producto_componente_id": "<medialuna>", "cantidad": 2 }
   ]}
   ```
3. **No** se le carga stock. Al venderlo se descuenta 1 café + 2 medialunas.

### E) Servicio

1. `POST /productos` — `tipo: "servicio"`. Y listo.

### F) Perecedero con lote (yogur, medicamento)

1. `POST /productos` — `"requiere_lote": true`
2. `POST /movimientos` `entrada` con `lote_nuevo` (código + `fecha_caducidad` + `costo`)
3. Al vender, descuenta solo del lote que vence primero (FEFO)
4. `GET /lotes/por-vencer` para ver qué está por caducar

### G) Bebida con 2x1 en la lata y mayoreo en la reja

1. `POST /productos` — unidad base = **lata**
2. `POST /productos/{id}/unidades` — "Reja x24", `factor: 24`
3. `POST /movimientos` `entrada` — cantidad en **latas**
4. `POST /api/v1/promociones` — `tipo: "nxm"`, `nxm_lleva: 2`, `nxm_paga: 1`,
   `objetivos: [{ "producto_id": "<id>" }]` → 2x1 en la lata
5. `POST /api/v1/promociones` — `tipo: "precio_fijo"`, `precio_fijo: 340`,
   `cantidad_minima: 5`, `objetivos: [{ "producto_unidad_id": "<id reja>" }]`
   → la reja a $340 llevando 5 o más

Al vender, cada línea agarra la promo que le corresponde y el descuento queda
congelado en el ticket.

---

## Editar un producto después

`PATCH /productos/{id}` — mandás **sólo los campos que cambian**. Los que no
mandás quedan igual.

- Para **borrar** la descripción o el código de barras (dejarlos vacíos) hay que
  mandar además el flag `cambiar_descripcion: true` / `cambiar_codigo_barras: true`.
  Es a propósito: sin el flag, "no lo mandé" significa "no lo toques". Lo mismo
  para el par de mayoreo: `cambiar_mayoreo: true` (con o sin `precio_mayoreo` /
  `cantidad_minima_mayoreo`; si no vienen, se limpian los dos) y
  `cambiar_instancia_capacidad_default: true`.
- Cambiar precio/costo suelto también se puede desde acá; pero lo normal es que
  el precio/costo se muevan solos con las compras (`actualizar_costo` en el
  movimiento).

Dar de baja / reactivar / borrar:
- `PATCH /productos/{id}/desactivar` (agregá `?confirmar_con_stock=true` si todavía
  tiene stock y aun así lo querés desactivar) — es lo normal.
- `PATCH /productos/{id}/activar`
- `DELETE /productos/{id}` — **borrado físico** (elimina también presentaciones,
  imágenes, lotes y existencia). Sólo funciona si el producto **nunca** tuvo
  movimientos ni ventas; si los tuvo, devuelve 409 y hay que usar `/desactivar`.
  Requiere el permiso `inventario.eliminar`.

---

## Errores comunes y qué significan

| Código | Mensaje típico | Qué pasó |
|--------|----------------|----------|
| 400 | "Ya existe un producto activo con el SKU …" | El SKU está en uso por otro producto activo |
| 400 | "…debe ser múltiplo de 0.0500" | La cantidad no respeta `incremento_minimo_venta` |
| 400 | "…no admite venta fraccionada: la cantidad debe ser entera" | Mandaste "2.5" en un producto `simple` |
| 400 | "Stock insuficiente para …" | La venta/salida dejaría el saldo en negativo y el producto no lo permite |
| 400 | "Indicá exactamente uno de `factor` o `unidades_por_base`" | En una presentación mandaste los dos, o ninguno |
| 400 | "…lleva control por lote: indicá `lote_id` o `lote_nuevo`" | Entrada de un producto con lote sin decir a qué lote |
| 400 | "No se puede activar el control por lote con stock cargado" | Intentaste poner `requiere_lote: true` con stock > 0 |
| 400 | "`precio_mayoreo` y `cantidad_minima_mayoreo` deben definirse juntos" | Mandaste uno solo del par de mayoreo |
| 400 | "`rastrea_instancia_abierta` requiere `instancia_capacidad_default` > 0" | Activaste el rastreo de envase abierto sin capacidad |
| 400 | "NxM debe cumplir `nxm_lleva > nxm_paga > 0`" | Promoción `nxm` con esos dos números mal (o faltando uno) |
| 400 | "`descuento_pct` debe estar en (0, 100]" | Promoción `porcentaje` con un % fuera de rango |
| 400 | "La promoción necesita al menos un producto o presentación objetivo" | Mandaste `objetivos: []` |
| 400 | "Cada objetivo lleva exactamente uno de `producto_id` o `producto_unidad_id`" | Un objetivo con los dos, o con ninguno |
| 400 / 409 | "Ya existe una promoción con nombre …" | El `nombre` de la promo está repetido |
| 409 | "…referenciado por ventas u otros registros históricos" | Quisiste `DELETE` un producto que ya tiene movimientos/ventas — usá `/desactivar` |
| 404 | "No existe el producto …" | El `id` está mal o el producto fue borrado |
| 409 | "El nombre … ya existe para este producto" | Dos presentaciones con el mismo nombre |
| 422 | (validación de formato) | Falta un campo obligatorio o el tipo de dato es incorrecto |

---

## Checklist para la pantalla "Nuevo producto"

- [ ] Selector de **categoría** (`GET /categorias`)
- [ ] Selector de **unidad de medida** (`GET /unidades-medida`), con opción "crear nueva"
- [ ] Selector de **tipo** (simple / fraccionable / kit / servicio) con ayuda contextual
- [ ] Campos: nombre, SKU, precio de venta, costo, impuesto, código de barras, descripción
- [ ] Si es **fraccionable**: mostrar campo "incremento mínimo de venta"
- [ ] Campos opcionales: **precio de mayoreo** + cantidad mínima (van juntos),
      checkbox **"precio con IVA incluido"**, checkbox **"sobre pedido"**
- [ ] Checkbox **"controlar por lote"** (`requiere_lote`) — deshabilitarlo si el producto ya tiene stock
- [ ] Checkbox **"rastrear envase abierto"** (`rastrea_instancia_abierta`) + capacidad — para venta a granel de envases
- [ ] Sección opcional **"Otras formas de venta"** (presentaciones) — sólo si no es kit ni servicio
- [ ] Si es **kit**: sección **"Receta"** para elegir productos componentes y cantidades
- [ ] Sección **Fotos**: subir archivo (`/imagenes/upload`) o pegar URL externa; marcar portada
- [ ] Sección **Stock inicial por sucursal** (cantidad + costo + stock mínimo) — omitir para kit/servicio; si es **por lote**, pedir además código de lote + caducidad
- [ ] Al guardar: crear producto → presentaciones → imágenes → movimientos de entrada, en ese orden
- [ ] (Aparte del alta) Pantalla de **Promociones** (`/api/v1/promociones`): tipo
      2x1 / % / precio fijo, lista de productos o presentaciones objetivo,
      prioridad, sucursal y vigencia opcionales
