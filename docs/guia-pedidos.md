# Guía: pedidos / órdenes y envío a domicilio (para la app)

> Cómo implementar en el frontend las **órdenes** (ventas que se cotizan, se
> guardan y se facturan después) y el **envío a domicilio**.
> Todo cuelga de `/api/v1/pedidos`. Al facturar se emite una **venta** normal
> (ver `docs/guia-ventas-y-caja.md`), así que caja, stock, promociones,
> monedero y crédito funcionan igual.

---

## La idea en dos minutos

- Un **pedido** es una **cotización que se persiste**: líneas (producto +
  cantidad + precio) con el precio final ya calculado por el backend (mayoreo +
  promociones), más datos de entrega y de pago opcionales.
- Ciclo de vida (`estado`): **`borrador`** (editable, precio "vivo") →
  **`confirmado`** (el cliente aceptó, **precio congelado**) → **`facturado`**
  (se emitió la venta). En cualquier punto antes de facturar: **`cancelado`**.
- El **envío a domicilio** es un `tipo` de pedido. Además del `estado` de arriba,
  lleva un **`estado_entrega`** propio (`pendiente` → `en_preparacion` →
  `en_reparto` → `entregado` / `fallido`) y campos de dirección + repartidor.
- **Facturar** un pedido confirmado = crear la venta. **Requiere un turno de caja
  abierto** (igual que cualquier venta). Devuelve la venta completa; el pedido
  queda `facturado` con `venta_id`.
- **No hay reserva de stock.** El stock se descuenta **al facturar**. Si en ese
  momento no alcanza → error y el pedido queda `confirmado` para reintentar.
- El **envío / instalación / etc. son líneas normales** cuyo producto es de tipo
  **`servicio`** (los creás en el catálogo). No hay campo `costo_envio` ni
  producto mágico. Una línea de servicio se marca `es_servicio: true` y **necesita
  un responsable** (`asignado_a`, un usuario) para poder **confirmar** el pedido.
- Los **anticipos** (prepago, seña) se registran en el pedido y entran como
  **pagos de la venta** al facturar. El POS sólo cobra el `saldo_por_cobrar`.

---

## Los dos estados (importante para la UI)

```
estado (todos los pedidos)
  borrador ──confirmar──▶ confirmado ──facturar──▶ facturado   (terminal)
     │            │  ▲
     │            │  └── reabrir
     └─cancelar───┴───────────▶ cancelado                       (terminal)

estado_entrega (sólo tipo = domicilio / recoger; en mostrador es null)
  pendiente ─▶ en_preparacion ─▶ en_reparto ─▶ entregado        (terminal)
                    │     ▲            │
                    ▼     └──────┐     ▼
                 fallido ────────┘   fallido
  (fallido se puede reintentar: vuelve a en_preparacion o en_reparto)
```

- `estado` y `estado_entrega` son **independientes**. Un pedido puede estar
  `confirmado` + `en_reparto`, o `confirmado` + `entregado` (listo para facturar).
- `tipo`: `mostrador` (sin entrega), `domicilio` (con dirección + reparto),
  `recoger` (el cliente pasa; usa `estado_entrega` sin `en_reparto`).
- `canal`: `pos`, `web`, `telefono` (informativo, para reportes).

---

## Parte 1 — Endpoints

Todos devuelven el envelope estándar `{ success, data, meta, links }` y exigen
JWT. Entre paréntesis, el permiso.

```
POST   /api/v1/pedidos/                         crear            (pedidos.crear)
GET    /api/v1/pedidos/?<filtros>               listar           (pedidos.leer)
GET    /api/v1/pedidos/resumen                  contadores       (pedidos.leer)
GET    /api/v1/pedidos/{id}                     detalle          (pedidos.leer)
PATCH  /api/v1/pedidos/{id}                     editar (borrador) (pedidos.editar)
POST   /api/v1/pedidos/{id}/confirmar           borrador→confirmado (pedidos.confirmar)
POST   /api/v1/pedidos/{id}/reabrir             confirmado→borrador (pedidos.editar)
POST   /api/v1/pedidos/{id}/cancelar            → cancelado       (pedidos.cancelar)
PATCH  /api/v1/pedidos/{id}/entrega             repartidor + estado_entrega (pedidos.repartir)
PATCH  /api/v1/pedidos/{id}/asignaciones        responsable de líneas de servicio (pedidos.editar)
POST   /api/v1/pedidos/{id}/anticipos           registrar anticipo (pedidos.editar)
POST   /api/v1/pedidos/{id}/facturar            emitir la venta   (pedidos.facturar)
```

Reparto de permisos por rol (seed de la migración): **admin** y **gerente**
tienen todo; **cajero** todo menos `pedidos.repartir`; **repartidor** (si existe
el rol) sólo `pedidos.leer` y `pedidos.repartir`.

### 1.1 Crear un pedido

```
POST /api/v1/pedidos/
Idempotency-Key: <uuid opcional>
{
  "tipo": "domicilio",                 // mostrador | domicilio | recoger
  "canal": "web",                      // pos | web | telefono   (default: pos)
  "lineas": [
    { "producto_id": "<coca>", "cantidad": 2, "precio_unitario": 200,
      "descuento_linea": 0, "impuesto_tasa": 16, "producto_unidad_id": null },
    { "producto_id": "<servicio-entrega>", "cantidad": 1, "precio_unitario": 50,
      "asignado_a": "<usuario-repartidor>" }   // línea de servicio: lleva responsable
  ],
  "cliente_id": null,                  // opcional
  "telefono": "5551234567",            // opcional (historial + monedero al facturar)
  "descuento_total": 0,                // descuento manual sobre el total
  "motivo_descuento": null,            // OBLIGATORIO si hay descuento manual (>0)
  "codigo_cupon": null,                // cupón que habilita una promo
  "cliente_segmento": null,            // hint para promos por segmento
  "notas": "Portón negro",
  "fecha_promesa": "2026-09-10T18:00:00Z",
  "direccion_texto": "Av Siempre Viva 742",   // OBLIGATORIO si tipo = domicilio
  "referencia_direccion": "entre 1ra y 2da",
  "confirmar": false                   // true = nace ya confirmado (precio congelado)
}
```

- La **sucursal** sale del usuario autenticado (sin sucursal → 400).
- El backend **recalcula el precio** de cada línea (mayoreo + promociones), igual
  que `POST /ventas/cotizar`. El `precio_unitario` que manda el POS se respeta
  sólo si no hay mayoreo/promo que lo pise.
- **No toca stock.** El detalle trae info de precio, no de disponibilidad. Si
  necesitás mostrar "hay stock", usá `POST /ventas/cotizar` con las mismas líneas
  (devuelve `hay_stock` por línea) antes de crear.
- `tipo = domicilio` sin `direccion_texto` → 400 `DireccionEnvioRequerida`.
- **Servicios**: cualquier línea cuyo producto sea de tipo `servicio` (envío,
  instalación, …) vuelve en el detalle con `es_servicio: true`. `asignado_a` (un
  usuario) es el responsable; se puede mandar al crear o después (ver 1.8). Se
  ignora en líneas que no son servicio.
- Respuesta: el pedido completo (ver 1.4). Guardá el `id`.

### 1.2 Editar un pedido (sólo en `borrador`)

```
PATCH /api/v1/pedidos/{id}
{ "tipo": "mostrador", "lineas": [ … ], "direccion_texto": "…", "notas": "…" }
```

- Sólo las claves presentes en el body se aplican (patch parcial).
- Se puede editar cualquier campo del alta, **incluido `tipo` y `canal`**.
  Al cambiar `tipo`:
  - a **`mostrador`**: se limpian `estado_entrega`, `direccion_texto`,
    `referencia_direccion` y `repartidor_id`. El front puede mandar
    `direccion_texto: null` sin que falle. (Sacá la línea de envío del carrito.)
  - a **`domicilio`**: exige `direccion_texto` (mandalo en el mismo PATCH) →
    si falta, 400 `DireccionEnvioRequerida`. Arranca `estado_entrega:"pendiente"`.
  - a **`recoger`**: arranca `estado_entrega:"pendiente"`, sin dirección obligatoria.
- Si mandás `lineas`, `descuento_total`, `codigo_cupon` o `cliente_segmento`, el
  backend **vuelve a cotizar** y reemplaza las líneas. Al mandar `lineas` incluí
  el `asignado_a` de cada línea de servicio (si no, se pierde). Para tocar sólo el
  responsable sin re-cotizar, usá `PATCH /{id}/asignaciones` (ver 1.8).
- Si el pedido no está en `borrador` → 400 `PedidoNoEditable`. Para editar uno
  `confirmado`: primero `POST /{id}/reabrir`.

### 1.3 Confirmar / reabrir / cancelar

```
POST /api/v1/pedidos/{id}/confirmar     // recotiza una última vez y CONGELA el precio
POST /api/v1/pedidos/{id}/reabrir       // vuelve a borrador para seguir editando
POST /api/v1/pedidos/{id}/cancelar      { "motivo": "el cliente se arrepintió" }
```

- `confirmar` desde algo que no es `borrador` → 409 `TransicionPedidoInvalida`.
- `confirmar` con una línea de servicio **sin `asignado_a`** → 400
  `ServicioSinResponsable`. Asigná el responsable antes (en el PATCH de líneas o
  en `PATCH /{id}/asignaciones`).
- `cancelar` un pedido `facturado` → 409 `PedidoYaFacturado` (para revertir una
  venta ya emitida se usa anular/devolución de ventas).
- `cancelar` con anticipos vivos: los marca `reembolsado` y dispara un evento
  `PedidoReembolsoRequerido`. **El reembolso real es manual / fuera de banda** —
  la app debería avisar "hay que devolver $X al cliente".

### 1.4 Detalle de un pedido

```
GET /api/v1/pedidos/{id}
```

```json
{
  "id": "…",
  "sucursal_id": "…",
  "usuario_id": "…",                    // quien lo creó
  "cliente_id": null,
  "tipo": "domicilio",
  "canal": "web",
  "estado": "confirmado",
  "estado_entrega": "en_preparacion",   // null si tipo = mostrador
  "telefono": "5551234567",
  "descuento_total": "0.00",
  "motivo_descuento": null,
  "codigo_cupon": null,
  "cliente_segmento": null,
  "notas": "Portón negro",
  "fecha_promesa": "2026-09-10T18:00:00Z",
  "direccion_texto": "Av Siempre Viva 742",
  "referencia_direccion": "entre 1ra y 2da",
  "repartidor_id": null,
  "entrega_fallo_motivo": null,
  "despachado_en": null,
  "entregado_en": null,
  "venta_id": null,                     // se llena al facturar
  "created_at": "2026-09-09T15:00:00Z",

  "subtotal": "620.00",                 // Σ subtotal de líneas (ya con mayoreo/promo)
  "total": "620.00",                    // subtotal − descuento_total
  "total_promociones": "0.00",          // informativo, ya restado en subtotal
  "total_anticipos": "100.00",          // anticipos no reembolsados
  "saldo_por_cobrar": "520.00",         // total − total_anticipos  → esto cobra el POS

  "lineas": [
    { "id": "…", "producto_id": "<coca>", "producto_unidad_id": null,
      "cantidad": "3.0000", "cantidad_en_unidad_base": "3.0000",
      "precio_unitario": "190.00", "descuento_linea": "0.00", "impuesto_tasa": "16.00",
      "promo_id": null, "promo_etiqueta": "Mayoreo x3", "promo_descuento": "0.00",
      "subtotal": "570.00", "es_servicio": false, "asignado_a": null },
    { "id": "…", "producto_id": "<servicio-entrega>", "producto_unidad_id": null,
      "cantidad": "1.0000", "cantidad_en_unidad_base": "1.0000",
      "precio_unitario": "50.00", "descuento_linea": "0.00", "impuesto_tasa": "0.00",
      "promo_id": null, "promo_etiqueta": null, "promo_descuento": "0.00",
      "subtotal": "50.00", "es_servicio": true, "asignado_a": "<usuario>" }
  ],
  "pagos": [
    { "id": "…", "monto": "100.00", "metodo_pago": "tarjeta_debito",
      "referencia": "stripe_pi_123", "reembolsado": false,
      "created_at": "2026-09-09T15:05:00Z" }
  ]
}
```

### 1.5 Listar pedidos (tablero)

```
GET /api/v1/pedidos/?estado=confirmado&tipo=domicilio&estado_entrega=en_reparto
                    &sucursal_id=…&cliente_id=…&repartidor_id=…&telefono=…
                    &canal=web&desde=2026-09-01&hasta=2026-09-30
                    &page=1&page_size=20&sort=created_at:desc      // o fecha_promesa:asc
```

Devuelve **items livianos** (sin `lineas` ni `pagos`): `id`, `tipo`, `canal`,
`estado`, `estado_entrega`, `telefono`, `cliente_id`, `repartidor_id`, `total`,
`saldo_por_cobrar`, `fecha_promesa`, `venta_id`, `created_at`. Para el detalle
completo, `GET /{id}`.

### 1.6 Contadores para el tablero

```
GET /api/v1/pedidos/resumen?sucursal_id=…
```

```json
{
  "por_estado":         { "borrador": 3, "confirmado": 12, "facturado": 40, "cancelado": 2 },
  "por_estado_entrega": { "pendiente": 4, "en_preparacion": 5, "en_reparto": 3, "entregado": 40, "fallido": 1 }
}
```

Ideal para las columnas de un kanban o los badges de un filtro.

### 1.7 Entrega: asignar repartidor y avanzar estado

```
PATCH /api/v1/pedidos/{id}/entrega
{ "estado_entrega": "en_reparto", "repartidor_id": "…", "motivo": null }
```

- Se puede mandar sólo `repartidor_id`, sólo `estado_entrega`, o ambos.
- Transición inválida (ej. `pendiente` → `en_reparto` salteando `en_preparacion`)
  → 409 `TransicionPedidoInvalida`.
- `estado_entrega = "fallido"` **exige** `motivo` → 409 si falta.
- Timestamps automáticos: `despachado_en` al pasar a `en_reparto`, `entregado_en`
  al pasar a `entregado`.
- Sobre un pedido `mostrador` (sin entrega) → 409 `EntregaNoAplica`.

### 1.8 Asignar el responsable de un servicio

```
PATCH /api/v1/pedidos/{id}/asignaciones
{ "asignaciones": [ { "detalle_id": "<id de la línea>", "asignado_a": "<usuario>" } ] }
```

- Fija/reasigna el responsable de líneas de **servicio** sin re-cotizar (no se
  pierden ids ni el resto de asignaciones).
- Vale en `borrador` **y** en `confirmado` (reasignar un repartidor/técnico
  después de confirmar). En `facturado`/`cancelado` → 409.
- `detalle_id` tiene que ser una línea `es_servicio: true` del pedido, si no →
  400 `ResponsableInvalido`. `asignado_a` tiene que ser un usuario activo.
- Alternativa: mandar el `asignado_a` dentro de cada línea en `PATCH /{id}`
  (pero eso re-cotiza y regenera los ids de línea).

### 1.9 Anticipos (prepago / seña)

```
POST /api/v1/pedidos/{id}/anticipos
{ "monto": 100.00, "metodo_pago": "tarjeta_debito", "referencia": "stripe_pi_123" }
```

- `metodo_pago`: cualquiera de ventas **menos `credito`** (`efectivo`,
  `tarjeta_credito`, `tarjeta_debito`, `transferencia`, `monedero`). `monto` > 0.
- No se puede sobre un pedido `facturado` o `cancelado` → 409.
- Baja el `saldo_por_cobrar` del pedido. Al facturar, cada anticipo se agrega
  como un pago de la venta.

### 1.10 Facturar (emitir la venta)

```
POST /api/v1/pedidos/{id}/facturar
Idempotency-Key: <uuid opcional>
{
  "caja_turno_id": "…",                // turno ABIERTO (obligatorio)
  "pagos": [
    { "monto": 500.00, "metodo_pago": "efectivo", "monto_recibido": 500.00 }
  ],
  "recalcular_precios": false          // ver abajo
}
```

- El pedido debe estar **`confirmado`** (si está en `borrador` → 409; hay que
  confirmarlo primero).
- **`pagos`** son los pagos del momento de facturar. Los **anticipos** del pedido
  se suman solos. Total a cubrir = `total` del pedido; lo que el POS pide cobrar
  ahora es el `saldo_por_cobrar`. Si `Σ pagos + anticipos < total` y hay
  `cliente_id` → el resto queda a **crédito** del cliente (mismas reglas que una
  venta normal); sin cliente → 400 `VentaCreditoSinCliente`.
- **`recalcular_precios`**:
  - `false` (default): se respeta **el precio congelado del pedido**. Lo que
    cotizaste es lo que se cobra.
  - `true`: se vuelven a correr mayoreo + promociones **vigentes al momento de
    facturar** (por si cambiaron desde que se confirmó).
- **Servicios / envío**: no hay nada especial acá. Las líneas de servicio del
  pedido (envío, instalación, …) se facturan como cualquier otra línea; el
  `asignado_a` queda en el pedido (no se copia a la venta).
- **Stock**: se descuenta acá. Si una línea deja stock negativo → 400
  `StockInsuficiente` y **no se factura** (el pedido sigue `confirmado`).
- Respuesta: **la venta completa**, con el mismo formato que `GET /ventas/{id}`
  (líneas, pagos, `total`, `cambio`, `estado` `pagada`/`pendiente_pago`, …). El
  pedido queda `facturado` con `venta_id`.
- **Idempotente**: reintentar con el pedido ya `facturado` devuelve la misma
  venta (no cobra dos veces). Mandá `Idempotency-Key` igual.
- Después de facturar: ticket en `GET /ventas/{venta_id}/ticket` (PDF).

---

## Parte 2 — Errores

| Código | Error | Qué pasó |
|---|---|---|
| 404 | `PedidoNoEncontrado` | El `id` no existe |
| 409 | `TransicionPedidoInvalida` | Cambio de estado no permitido (confirmar algo no-borrador, facturar algo no-confirmado, transición de entrega ilegal, `fallido` sin motivo) |
| 409 | `PedidoYaFacturado` | Cancelar / editar un pedido ya facturado |
| 409 | `EntregaNoAplica` | Operación de entrega sobre un pedido `mostrador`, o facturar una entrega `fallido` |
| 400 | `DireccionEnvioRequerida` | `tipo = domicilio` sin `direccion_texto` |
| 400 | `PedidoNoEditable` | `PATCH` sobre un pedido que no está en `borrador` |
| 400 | `PedidoSinLineas` | Pedido sin líneas |
| 400 | `MotivoDescuentoRequerido` | Hay descuento manual (`descuento_total`/`descuento_linea` > 0) sin `motivo_descuento` |
| 400 | `AnticipoInvalido` | Anticipo ≤ 0 o con `metodo_pago = "credito"` |
| 400 | `ServicioSinResponsable` | `confirmar` con una línea `es_servicio` sin `asignado_a` |
| 400 | `ResponsableInvalido` | `asignado_a` no es un usuario activo, o la línea de `PATCH /asignaciones` no es un servicio |
| 422 | (formato) | Falta un campo o el tipo es inválido (`cantidad ≤ 0`, enum inválido, …) |

Al **facturar**, además pueden salir todos los errores de una venta normal:
`CajaNoAbierta`, `TurnoDeOtraSucursal`, `StockInsuficiente`,
`LimiteCreditoExcedido`, `VentaCreditoSinCliente`, `SucursalNoOperativa`,
`CuponVencido` / `CuponAgotado`, `SaldoMonederoInsuficiente`, … → ver
**Parte 5 de `docs/guia-ventas-y-caja.md`**. En todos, la venta **no se crea** y
el pedido sigue `confirmado`.

---

## Parte 3 — Plan de implementación en el frontend

Por orden de valor. Cada fase es entregable sola.

### Fase A — Órdenes de mostrador (cotizar → confirmar → facturar)

Cubre "ventas que se cotizan y se cobran después". Sin envío.

1. **Lista de pedidos** — `GET /pedidos/` + `GET /pedidos/resumen`.
   - Tabla/kanban por `estado`. Filtros: `estado`, `tipo`, `canal`, rango de
     fechas, `cliente_id`, `telefono`.
   - Badges con los contadores de `/resumen`.
2. **Alta de pedido** — reusar el **carrito del POS** (buscador de productos,
   cantidad, precio, presentación, descuento por línea).
   - Preview de totales/promos con `POST /ventas/cotizar` (ya existe) en cada
     cambio del carrito.
   - `POST /pedidos/` con `tipo: "mostrador"`. Botón "Guardar borrador" vs
     "Guardar y confirmar" (`confirmar: true`).
   - Mandar `Idempotency-Key`.
3. **Detalle de pedido** — `GET /pedidos/{id}`. Acciones según `estado`:
   - `borrador`: Editar (`PATCH`), Confirmar, Cancelar.
   - `confirmado`: Reabrir, Cancelar, **Facturar**.
   - `facturado`: link a la venta / ticket (`venta_id`).
4. **Editar** — mismo carrito, `PATCH /pedidos/{id}`. Sólo visible en `borrador`.
5. **Confirmar** — `POST /{id}/confirmar`. Mostrar el `total` que devuelve
   (precio ya congelado) y avisar "el precio queda fijo".
6. **Facturar** — modal de cobro:
   - Precondición: turno abierto → `GET /caja-turnos/actual` (si no hay, bloquear
     y ofrecer "Abrir caja", igual que el POS).
   - Cobrar el `saldo_por_cobrar`; uno o varios `pagos` con método; campo
     "recibí con" → `monto_recibido` en efectivo.
   - `POST /{id}/facturar` con `caja_turno_id` + `Idempotency-Key`.
   - Al volver: navegar al **ticket** (`GET /ventas/{venta_id}/ticket`).
   - Manejar `StockInsuficiente` / `LimiteCreditoExcedido` sin perder la pantalla
     (el pedido sigue `confirmado`, se puede reintentar).
7. **Cancelar** — `POST /{id}/cancelar` con `motivo`.

### Fase B — Envío a domicilio

8. Selector de **`tipo`** (`mostrador` / `domicilio` / `recoger`) en el alta **y
   en la edición mientras esté en `borrador`** (`PATCH` con `tipo`; al pasar a
   `domicilio` hay que mandar `direccion_texto` en el mismo request).
   Con `domicilio`: campos `direccion_texto` (obligatorio), `referencia_direccion`,
   `fecha_promesa`.
8b. **Línea de servicio de envío**: selector de servicios del catálogo
   (`GET /api/v1/inventario/productos/buscar?tipo=servicio&activo=true`); al
   agregar la línea, **exigir elegir el responsable** (`asignado_a`, picker de
   usuarios filtrado por rol repartidor). Si `tipo = domicilio` y no hay ninguna
   línea de servicio, sugerir agregar "Entrega a domicilio". El precio de la
   línea sale del catálogo o lo edita el operador (envío por zona).
9. **Tablero de entregas** — `GET /pedidos/?tipo=domicilio&estado_entrega=…`.
   Columnas: `pendiente`, `en_preparacion`, `en_reparto`, `entregado`, `fallido`
   (contadores de `/resumen.por_estado_entrega`).
10. **Acciones de entrega** — `PATCH /{id}/entrega`:
    - Asignar repartidor del pedido (`repartidor_id`; lista de usuarios del rol
      repartidor). Es aparte del `asignado_a` de la línea de servicio: uno es
      "quién lleva el pedido", el otro "quién ejecuta ese servicio".
    - Botón "Siguiente estado" respetando las transiciones del diagrama.
    - "Marcar entrega fallida" → pide `motivo`; después permite reintentar.
    - Mostrar `despachado_en` / `entregado_en`.
11. En el detalle, sección "Entrega" con dirección, repartidor, timeline de
    estados, y el `asignado_a` de cada servicio (editable vía
    `PATCH /{id}/asignaciones`, también en `confirmado`).

### Fase C — Prepago y cierre fino

12. **Anticipos** — en el detalle (`borrador`/`confirmado`): form
    `monto` + `metodo_pago` + `referencia`; `POST /{id}/anticipos`. Mostrar
    `total_anticipos` y `saldo_por_cobrar`. En el modal de facturar, cobrar sólo
    el `saldo_por_cobrar`.
13. **Cancelación con reembolso** — si `total_anticipos > 0`, el modal de cancelar
    avisa "hay que reembolsar $X" (el backend sólo marca `reembolsado` y emite el
    evento; la devolución del dinero la hace una persona).
14. **Facturar con `recalcular_precios: true`** — checkbox opcional "usar precios
    de hoy" para pedidos viejos cuya promo/mayoreo cambió.
15. **Canal `web`** — si hay tienda online, los pedidos entran con `canal: "web"`;
    el mismo tablero los muestra. (El endpoint de creación hoy exige JWT; para un
    storefront público habría que exponer un alta anónima — pedir al backend.)

### Roles / visibilidad

- Ocultar **Facturar** si el usuario no tiene `pedidos.facturar`.
- **Editar / Confirmar / Cancelar** → `pedidos.editar` / `pedidos.confirmar` /
  `pedidos.cancelar`.
- Tablero y acciones de **entrega** → `pedidos.repartir` (un repartidor ve la
  lista y cambia `estado_entrega`, nada más).

---

## Parte 4 — Flujos completos

### 4.1 Orden de mostrador que se cobra al otro día
1. `POST /pedidos/` `{ tipo:"mostrador", lineas:[…] }` → `borrador`.
2. (opcional) `PATCH /pedidos/{id}` para ajustar.
3. `POST /pedidos/{id}/confirmar` → `confirmado`, precio congelado.
4. Al día siguiente, con turno abierto: `POST /pedidos/{id}/facturar`
   `{ caja_turno_id, pagos:[{monto: total, metodo_pago:"efectivo"}] }` → venta.

### 4.2 Envío a domicilio, pago contra entrega
1. `POST /pedidos/` `{ tipo:"domicilio", direccion_texto:"…", confirmar:true,
   lineas:[ <productos>, { producto_id:"<servicio-entrega>", cantidad:1,
   precio_unitario:30, asignado_a:"<repartidor>" } ] }`.
2. Cocina: `PATCH /{id}/entrega { estado_entrega:"en_preparacion" }`.
3. Sale el repartidor: `PATCH /{id}/entrega { estado_entrega:"en_reparto", repartidor_id:"…" }`.
4. Entregado y cobrado: `PATCH /{id}/entrega { estado_entrega:"entregado" }`.
5. `POST /{id}/facturar { caja_turno_id, pagos:[{monto: total, metodo_pago:"efectivo"}] }`
   → venta con la línea de envío incluida.

### 4.3 Envío con prepago online
1. `POST /pedidos/` `{ tipo:"domicilio", …, canal:"web", lineas:[…, línea de servicio] }`.
2. `POST /{id}/anticipos { monto: total, metodo_pago:"tarjeta_credito", referencia:"…" }`
   → `saldo_por_cobrar` queda en 0.
3. `POST /{id}/confirmar`.
4. Entrega (pasos 2-4 del flujo 4.2).
5. `POST /{id}/facturar { caja_turno_id, pagos: [] }` → venta pagada (el anticipo
   cubre todo).

### 4.4 Entrega fallida
1. `PATCH /{id}/entrega { estado_entrega:"fallido", motivo:"nadie en el domicilio" }`.
2. Reintentar: `PATCH /{id}/entrega { estado_entrega:"en_reparto" }` → y de nuevo
   `entregado`. O `POST /{id}/cancelar { motivo:"no se pudo entregar" }` (si hubo
   anticipo, avisar del reembolso).

---

## Parte 5 — Checklist para el frontend

- [ ] Lista/tablero de pedidos con filtros (`estado`, `tipo`, `estado_entrega`,
      `canal`, fechas, `cliente`/`telefono`) + contadores de `/resumen`
- [ ] Alta de pedido reusando el carrito del POS; preview con `POST /ventas/cotizar`
- [ ] Selector de `tipo`; con `domicilio`: `direccion_texto` (obligatorio),
      `referencia_direccion`, `fecha_promesa`
- [ ] Línea de servicio de envío desde el catálogo (`?tipo=servicio`); al agregarla,
      exigir `asignado_a` (responsable). Bloquear "Confirmar" si algún servicio no
      tiene responsable (evita el 400 `ServicioSinResponsable`)
- [ ] Reasignar responsable de un servicio con `PATCH /{id}/asignaciones` (sirve en
      `confirmado`)
- [ ] `Idempotency-Key` en `POST /pedidos/` y en `POST /{id}/facturar`
- [ ] Detalle con acciones condicionadas por `estado` (borrador / confirmado /
      facturado / cancelado) y por permisos
- [ ] Editar sólo en `borrador`; si está `confirmado`, ofrecer "Reabrir"
- [ ] Confirmar: mostrar el `total` congelado y avisar que el precio queda fijo
- [ ] Facturar: chequear `GET /caja-turnos/actual`; cobrar el `saldo_por_cobrar`;
      `monto_recibido` en efectivo; al terminar ir al ticket de la venta
- [ ] Manejar `StockInsuficiente` / `LimiteCreditoExcedido` / `VentaCreditoSinCliente`
      en el facturar sin perder la pantalla (el pedido sigue `confirmado`)
- [ ] Tablero de entregas por `estado_entrega`; botón "siguiente estado" según las
      transiciones; "entrega fallida" pide `motivo`
- [ ] Asignar repartidor (`PATCH /{id}/entrega` con `repartidor_id`)
- [ ] Anticipos: form + mostrar `total_anticipos` y `saldo_por_cobrar`
- [ ] Cancelar con `motivo`; si hay anticipos, avisar "reembolsar $X" (manual)
- [ ] Ocultar acciones sin permiso (`pedidos.facturar`, `pedidos.repartir`, …)
- [ ] `sort=fecha_promesa:asc` para la vista "próximas entregas"
