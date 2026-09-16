# Guía: consumir `/api/v1/reportes` desde el frontend

> Módulo de **solo lectura**: agrega datos de ventas, inventario y clientes.
> No hay POST/PUT/DELETE en este módulo. Todo cuelga de `/api/v1/reportes`.

---

## 0. Antes de pedir nada

**Auth**: header `Authorization: Bearer <token>` en toda request (login en
`POST /api/v1/usuarios/login`).

**Permisos** (2, cada uno gatilla una parte distinta de la UI):
- `reportes.leer`: ver cualquier reporte en JSON (los 9 endpoints, dashboard
  incluido). Sin esto, ocultar toda la sección "Reportes".
- `reportes.exportar`: además de leer, descargar en CSV/Excel/PDF (`?formato=`,
  ver sección 3). Sin esto, ocultar el botón "Exportar" pero dejar la vista
  JSON normal — el backend devuelve `403` solo en la rama de export, `leer`
  sigue funcionando igual.

**Sucursal**: los reportes con filtro `sucursal_id` se comportan así:
- Roles **globales** (admin/gerente): pueden mandar `sucursal_id` o
  omitirlo (`null` = todas las sucursales agregadas).
- Cualquier otro rol: el backend **ignora** el `sucursal_id` que mandes y
  fuerza el del propio usuario. Si ese usuario no tiene sucursal asignada,
  responde `400`.

  → Conclusión para el front: **mostrar el selector de sucursal solo si
  `usuario.rol` es global**; para el resto, ni mostrarlo (no rompe nada si lo
  mandás, pero es ruido — el resultado siempre es el de su propia sucursal).

---

## 1. El sobre de respuesta (igual en toda la API, no solo reportes)

Éxito, recurso singular (sin paginar):
```json
{
  "success": true,
  "data": { "...": "..." }
}
```
`meta`/`links` no aparecen en absoluto cuando no aplican (no vienen como
`null` ni como objeto vacío) — no hace falta chequear su existencia si el
endpoint es de un solo objeto.

Éxito, listado paginado (`ventas-por-usuario`, `productos-mas-vendidos`,
`clientes-con-saldo`):
```json
{
  "success": true,
  "data": [ { "...": "..." } ],
  "meta": {
    "pagination": {
      "page": 1, "page_size": 20,
      "total_items": 87, "total_pages": 5,
      "has_next": true, "has_prev": false
    },
    "filters": { "desde": "2026-08-01T00:00:00", "hasta": "2026-08-31T23:59:59", "sucursal_id": "..." }
  },
  "links": {
    "self": "https://.../reportes/ventas-por-usuario?page=1&page_size=20",
    "next": "https://.../reportes/ventas-por-usuario?page=2&page_size=20",
    "prev": null
  }
}
```
Paginación: query params `page` (1-indexada, default 1) y `page_size`
(default 20, máx 100). Para "siguiente página" **no armes la URL a mano**:
usá `links.next` tal cual vino (ya trae todos los filtros/sort).

Error (cualquier 4xx/5xx, formato único):
```json
{
  "success": false,
  "error": {
    "code": "FORBIDDEN",
    "message": "No tienes permiso para esta acción",
    "fields": null
  }
}
```
`code` es uno de: `BAD_REQUEST`, `UNAUTHORIZED`, `FORBIDDEN`, `NOT_FOUND`,
`VALIDATION_ERROR` (422, trae `fields: {campo: [errores]}`), `INTERNAL_ERROR`.
Alcanza con un manejador de errores genérico por `code`, no hace falta uno
por endpoint.

---

## 2. Endpoints

Fechas (`desde`/`hasta`) son `datetime` ISO-8601 (no solo fecha). Si se
omiten, el backend usa por defecto **el último año** — no hace falta
mandarlas siempre, pero para un selector de rango real conviene mandarlas
explícitas.

| # | Endpoint | Params | Paginado | Export | Devuelve |
|---|---|---|---|---|---|
| 1 | `GET /corte-caja/{caja_turno_id}` | — | no | sí | corte de una sesión de caja puntual |
| 2 | `GET /ventas` | `desde, hasta, sucursal_id` | no | sí | totales del período + desglose por día |
| 3 | `GET /ventas-por-metodo-pago` | `desde, hasta, sucursal_id` | no | sí | distribución efectivo/tarjeta/transferencia/crédito/monedero |
| 4 | `GET /ventas-por-usuario` | `desde, hasta, sucursal_id` + paginación | **sí** | sí | ranking de cajeros/vendedores |
| 5 | `GET /productos-mas-vendidos` | `desde, hasta, sucursal_id` + paginación | **sí** | sí | ranking de productos por cantidad |
| 6 | `GET /inventario-valorizado` | `sucursal_id, categoria_id` | no | sí | valor de stock a costo, por categoría |
| 7 | `GET /mermas-ajustes` | `desde, hasta, sucursal_id` | no | sí | totales de merma/ajuste de inventario |
| 8 | `GET /clientes-con-saldo` | `sucursal_id` + paginación | **sí** | sí | clientes con saldo de crédito pendiente |
| 9 | `GET /dashboard` | `sucursal_id` | no | no | KPIs del día: ventas hoy vs. ayer, top 3 productos, stock bajo, cajas abiertas |

"Export" = acepta `?formato=csv\|excel\|pdf` (sección 3). `/dashboard` no
exporta — es una vista viva, no un reporte para archivar/imprimir.

### 2.1 Corte de caja — `GET /corte-caja/{caja_turno_id}`
```json
{ "data": {
  "caja_turno_id": "uuid",
  "monto_inicial": "500.00",
  "total_efectivo": "1200.00",
  "total_tarjeta": "800.00",
  "total_transferencia": "150.00",
  "total_credito": "0.00",
  "total_monedero": "50.00",
  "monto_final_esperado": "1650.00",
  "total_descuento_promo": "35.00",
  "total_devoluciones_efectivo": "20.00",
  "total_ingresos": "0.00",
  "total_retiros": "100.00",
  "total_gastos": "30.00",
  "nota": "Solo el efectivo se considera para el arqueo físico de caja."
}}
```
`404` si el `caja_turno_id` no existe.

### 2.2 Ventas por período — `GET /ventas`
```json
{ "data": {
  "desde": "2026-08-01T00:00:00", "hasta": "2026-08-31T23:59:59",
  "sucursal_id": null,
  "total_vendido": "45230.50", "numero_ventas": 312,
  "ticket_promedio": "145.03", "total_descuento_promo": "890.00",
  "por_dia": [ { "dia": "2026-08-01", "numero_ventas": 12, "total": "1740.00" } ]
}}
```
`400` si `desde > hasta`.

### 2.3 Ventas por método de pago — `GET /ventas-por-metodo-pago`
```json
{ "data": {
  "desde": "...", "hasta": "...", "sucursal_id": null,
  "total_efectivo": "20000", "total_tarjeta": "15000",
  "total_transferencia": "5000", "total_credito": "3000", "total_monedero": "2230.50",
  "total_general": "45230.50",
  "detalle": [ { "metodo_pago": "efectivo", "total": "20000" } ]
}}
```
`detalle` es el desglose crudo por valor exacto de `metodo_pago` (incluye
`tarjeta_credito`/`tarjeta_debito` separados); los `total_*` de arriba ya
vienen agrupados para pintar directo un gráfico de torta.

### 2.4 Ventas por usuario (paginado) — `GET /ventas-por-usuario`
```json
{ "data": [
  { "usuario_id": "uuid", "nombre": "Ana Pérez", "numero_ventas": 45, "total_vendido": "12300.00" }
], "meta": { "pagination": { "...": "..." } } }
```
Orden: de mayor a menor `total_vendido` (no hay `?sort=` en este endpoint).

### 2.5 Productos más vendidos (paginado) — `GET /productos-mas-vendidos`
```json
{ "data": [
  { "producto_id": "uuid", "sku": "REF-001", "nombre": "Coca-Cola 600ml",
    "cantidad_vendida": "230.0000", "monto_total": "3450.00" }
], "meta": { "pagination": { "...": "..." } } }
```
`cantidad_vendida` es `Decimal` con 4 decimales (hay productos fraccionables,
p. ej. kg) — no lo trates como entero al formatear.

### 2.6 Inventario valorizado — `GET /inventario-valorizado`
```json
{ "data": {
  "sucursal_id": null, "categoria_id": null,
  "valor_total": "125000.00",
  "por_categoria": [
    { "categoria_id": "uuid", "nombre": "Bebidas", "valor": "45000.00", "numero_productos": 32 }
  ]
}}
```
⚠️ `valor`/`valor_total` son **a costo** (`cantidad × costo`), no a precio de
venta. Si necesitás valorización a venta, todavía no existe — ver
[reportes-pendientes.md](reportes-pendientes.md).

### 2.7 Mermas y ajustes — `GET /mermas-ajustes`
```json
{ "data": {
  "desde": "...", "hasta": "...", "sucursal_id": null,
  "total_merma": "12.5000", "total_ajuste": "3.0000",
  "valor_estimado_total": "340.00",
  "detalle": [
    { "tipo": "merma", "numero_movimientos": 8, "cantidad_total": "12.5000", "valor_estimado": "290.00" },
    { "tipo": "ajuste", "numero_movimientos": 2, "cantidad_total": "3.0000", "valor_estimado": "50.00" }
  ]
}}
```
`valor_estimado` es aproximado: usa el `costo_unitario` capturado en cada
movimiento (puede venir `null` si el movimiento no lo registró, se trata
como 0 en ese caso).

### 2.8 Clientes con saldo (paginado) — `GET /clientes-con-saldo`
```json
{ "data": [
  { "cliente_id": "uuid", "nombre": "Juan López", "saldo_credito": "850.00", "limite_credito": "2000.00" }
], "meta": { "pagination": { "...": "..." } } }
```
Este es un stand-in de "cartera vencida" — cuando exista un módulo de
crédito dedicado, este endpoint podría moverse o desaparecer. No construir
nada que asuma que va a quedar acá para siempre.

### 2.9 Dashboard — `GET /dashboard`
```json
{ "data": {
  "sucursal_id": null,
  "ventas_hoy": { "...": "ReporteVentasResponse, ver 2.2" },
  "ventas_ayer": { "...": "mismo shape, comparado a la misma hora de ayer (no el día completo)" },
  "top_productos_hoy": [ { "...": "ProductoRankingResponse, ver 2.5, máx 3" } ],
  "productos_bajo_stock": 7,
  "cajas_abiertas": [
    { "sucursal_id": "uuid", "caja_turno_id": "uuid", "usuario_id": "uuid",
      "abierto_en": "2026-09-13T08:00:00Z", "saldo_inicial": "500.00" }
  ]
}}
```
Sin cache en el backend — cada llamada recalcula. Si se pintan varios
widgets del dashboard en pantalla, pedí este único endpoint y repartí sus
campos entre los widgets, no llames a `/ventas` + `/productos-mas-vendidos`
por separado para armar lo mismo.

---

## 3. Exportar a CSV/Excel/PDF (`?formato=`)

Los 8 reportes de la tabla (todos salvo `/dashboard`) aceptan
`?formato=csv|excel|pdf` además del default `json`. Con `formato != json` la
respuesta **no** es el sobre `{success, data, ...}` — es el archivo binario
directo, con:
```
Content-Type: text/csv | application/vnd.openxmlformats-officedocument.spreadsheetml.sheet | application/pdf
Content-Disposition: attachment; filename="ventas.csv"
```
Tratalo como una descarga de archivo normal (`window.open`, o un `<a>` que
apunte a la URL con el query param — el navegador dispara la descarga por el
`Content-Disposition`), no como una llamada JSON.

Requiere el permiso `reportes.exportar` además de `reportes.leer` — si falta,
da `403` con el sobre de error normal (esta rama sí devuelve JSON, es el
error, no el archivo). El resto de los query params (`desde`, `hasta`,
`sucursal_id`, paginación) se combinan igual que en la versión JSON.

---

## 4. Todos los `Decimal` viajan como **string**

Cada monto/cantidad (`total_vendido`, `cantidad_vendida`, `saldo_credito`,
etc.) serializa como **string** (`"1200.50"`), no como `number` de JSON —
es el comportamiento estándar de Pydantic con `Decimal` y evita el redondeo
de punto flotante de JS. Parsealo con una lib decimal-safe (o al menos
`parseFloat` solo para mostrar, nunca para sumar en el cliente si te importa
la precisión — mejor pedirle el total ya sumado al backend, que es lo que
estos endpoints ya hacen).

---

## 5. Qué falta (no construir UI para esto todavía)

- Ventas por categoría, comparativo de período, valorización a precio de
  venta → ver [reportes-pendientes.md](reportes-pendientes.md).
- Reportes programados / envío por correo (dashboard y export sí existen;
  esto no se llegó a construir).
