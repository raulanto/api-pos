# Guía: proveedores (catálogo, pedidos, recepción y devoluciones)

> Cómo administrar proveedores, enlazarlos a productos, disparar pedidos de
> reabasto cuando falta stock, recibir mercancía (con defectuosos) y
> devolverle al proveedor lo que llegó mal. Todo cuelga de
> `/api/v1/proveedores`, `/api/v1/pedidos-proveedor`,
> `/api/v1/recepciones-proveedor` y `/api/v1/devoluciones-proveedor`; el
> vínculo producto↔proveedor cuelga de `/api/v1/inventario`.

---

## La idea en dos minutos

- Un **proveedor** es un catálogo global (no por sucursal), con su propio
  `código` (lo elegís vos, como el `sku` de un producto).
- Un producto puede tener **varios proveedores** (N:N). Uno de ellos es el
  **principal**: el que se usa para el reabasto automático. Sólo puede haber
  un principal activo por producto.
- Cada vínculo producto-proveedor trae su propio `stock_minimo` (dispara el
  reabasto), `cantidad_reorden` (cuánto pedir) y `precio_compra`.
- El **motor de reorden** es manual (lo dispara alguien, no un cron): compara
  el stock real de cada sucursal contra ese `stock_minimo` y arma **pedidos en
  borrador** — nunca los envía solo.
- Confirmar el envío de un pedido, recibir la mercancía y devolver lo
  defectuoso son tres pasos separados y explícitos. Nada pasa "solo".
- Al **recibir** mercancía, lo bueno entra al stock de verdad (mismo mecanismo
  que cualquier entrada de inventario); lo defectuoso **nunca** entra a stock
  vendible — o se da de baja como merma, o queda pendiente de devolver.

---

## Parte 0 — Puesta en marcha

```bash
uv run alembic upgrade head        # head: 126350173815
```

Son 4 migraciones (una por fase): `proveedor`+`producto_proveedor`,
`pedido_proveedor`, `recepcion_proveedor`, `devolucion_proveedor`. Cada una
siembra sus propios permisos.

> **Ojo, no son la misma cosa:** `producto_proveedor.stock_minimo` (este
> módulo) y `existencia.stock_minimo` (el umbral de alerta genérico que ya
> existía en inventario) son dos campos **distintos**. El de `existencia` es
> sólo informativo/de alerta; el de `producto_proveedor` es el que **dispara
> el motor de reorden** con ese proveedor puntual, y es el mismo valor para
> todas las sucursales (la comparación sí es por sucursal, contra el stock
> real de cada una).

---

## Parte 1 — Proveedores

```
POST   /api/v1/proveedores
GET    /api/v1/proveedores?activo=&q=&page=&page_size=&sort=
GET    /api/v1/proveedores/{id}
PATCH  /api/v1/proveedores/{id}
PATCH  /api/v1/proveedores/{id}/desactivar
PATCH  /api/v1/proveedores/{id}/activar
```

```json
POST /api/v1/proveedores
{
  "codigo": "PROV-COCA", "razon_social": "Coca-Cola FEMSA",
  "tipo_persona": "moral", "condiciones_pago": "credito", "dias_credito": 30,
  "rfc": "CFE850101ABC", "telefono": "8112345678", "email": "ventas@femsa.com"
}
```

- `codigo` lo elegís vos, único entre proveedores **activos** (si desactivás
  uno, su código queda libre — mismo comportamiento que `producto.sku`).
- `condiciones_pago: "credito"` **exige** `dias_credito` (> 0); con `"contado"`
  se ignora/limpia solo. Si mandás `"credito"` sin días → 400
  `DiasCreditoRequerido`.
- `q` en el listado busca en código, razón social y RFC.
- Para borrar campos opcionales (RFC, teléfono, notas, etc.) en el `PATCH`,
  mandá el flag `cambiar_<campo>: true` (mismo patrón "flags explícitos" que
  el resto del sistema — sin el flag, "no lo mandé" = "no lo toques").

Permiso: `proveedores.leer` para consultar, `proveedores.crear` /
`proveedores.editar` para escribir.

```
GET /api/v1/proveedores/{id}/productos          // qué productos provee (ver Parte 2)
GET /api/v1/proveedores/{id}/resumen            // ver Parte 6
```

---

## Parte 2 — Vincular productos a proveedores

Cuelga del **producto** (no del proveedor), porque se piensa como "¿de dónde
consigo este producto?":

```
POST   /api/v1/inventario/productos/{producto_id}/proveedores
GET    /api/v1/inventario/productos/{producto_id}/proveedores?incluir_inactivos=
DELETE /api/v1/inventario/productos/{producto_id}/proveedores/{id}
PATCH  /api/v1/inventario/productos/{producto_id}/proveedores/{id}/marcar-principal
```

```json
POST /api/v1/inventario/productos/{producto_id}/proveedores
{
  "proveedor_id": "…",
  "precio_compra": 18.50,
  "tiempo_entrega_dias": 3,
  "stock_minimo": 20,
  "cantidad_reorden": 100,
  "codigo_proveedor": "SKU-DEL-PROVEEDOR-123",
  "es_proveedor_principal": true
}
```

- Un producto no puede tener **dos veces al mismo proveedor** activo
  (409 `ProductoProveedorYaExiste`).
- Sólo puede haber **un principal activo** por producto — pedirlo cuando ya
  hay otro da 409 `YaHayProveedorPrincipal`. Para cambiar el principal, no
  hace falta desvincular al viejo: `PATCH .../marcar-principal` en el nuevo
  vínculo lo quita del anterior automáticamente.
- `DELETE` es una baja **lógica** (`activo=false`); si era el principal, deja
  de serlo (nadie queda "principal inactivo").
- El principal es el que usa el **motor de reorden** (Parte 3) — un producto
  sin principal activo nunca genera pedidos automáticos, aunque tenga
  proveedores secundarios cargados.

Permiso: `producto_proveedor.gestionar` (escritura); lectura con ese permiso o
`proveedores.leer`.

---

## Parte 3 — Pedidos a proveedor y motor de reorden

### 3.1 Motor de reorden (disparo manual)

```
POST /api/v1/proveedores/reorden/evaluar?sucursal_id=
```

- Recorre todos los vínculos **principales y activos**, compara el stock real
  de esa sucursal contra `stock_minimo`, y agrupa lo que falta por proveedor.
- Por cada proveedor con algo por debajo del mínimo: si ya hay un pedido
  **`borrador`** generado automáticamente para ese proveedor+sucursal, le
  **suma** las líneas nuevas (no crea uno por corrida); si no hay, crea uno
  nuevo con `generado_automaticamente: true`.
- **Nunca envía nada solo.** El pedido queda en `borrador`, a la espera de que
  alguien lo revise y confirme (o lo cancele).
- Devuelve la lista de pedidos tocados, con `fue_creado: true/false` para que
  la UI distinga "pedido nuevo" de "se le agregó a uno que ya estaba abierto".

Permiso: `pedido_proveedor.generar_manual`.

### 3.2 Pedido manual (sin pasar por el motor)

```
POST /api/v1/pedidos-proveedor
{
  "proveedor_id": "…",
  "lineas": [{ "producto_id": "…", "cantidad_solicitada": 50, "precio_unitario": 18.50 }],
  "fecha_estimada_entrega": "2026-10-01"
}
```

Permiso `pedido_proveedor.gestionar`. La sucursal sale del usuario
autenticado. `subtotal` **no se guarda**: se calcula siempre desde las líneas
(mismo criterio que `Venta.total`/`Pedido.total` en el resto del sistema).

### 3.3 Ciclo de vida

```
borrador ──confirmar-envío──▶ enviado ──(recepción)──▶ parcial ⇄ recibido
   └──────────────────cancelar─────────────────────────────────▶ cancelado
```

```
POST /api/v1/pedidos-proveedor/{id}/confirmar-envio   // borrador -> enviado; permiso aparte
POST /api/v1/pedidos-proveedor/{id}/cancelar           // no se puede desde 'recibido'
```

- `confirmar-envio` tiene su **propio permiso** (`pedido_proveedor.
  confirmar_envio`, sólo admin/gerente) distinto de crear/cancelar
  (`pedido_proveedor.gestionar`, incluye almacenista) — separar "armar el
  pedido" de "autorizar que salga" fue explícito.
- `parcial`/`recibido` los pone **solo** el sistema, al procesar una recepción
  con `pedido_id` (Parte 4) — no hay endpoint para forzarlos a mano.
- El estado `confirmado` existe en la base pero **no tiene ninguna acción que
  lo dispare todavía** (quedó reservado para cuando haya un flujo real de "el
  proveedor confirmó el pedido").

Listado: `GET /api/v1/pedidos-proveedor?proveedor_id=&sucursal_id=&estado=`
(permiso `pedido_proveedor.leer`).

---

## Parte 4 — Recepción de mercancía

```
POST /api/v1/recepciones-proveedor
{
  "proveedor_id": "…",
  "pedido_id": "…",                       // opcional: si viene, actualiza el pedido
  "numero_factura": "FAC-00123",
  "numero_remision": "REM-556",
  "transportista": "DHL",
  "lineas": [
    {
      "producto_id": "…",
      "cantidad_esperada": 100,           // opcional, para calcular si vino completo
      "cantidad_recibida_buena": 90,
      "cantidad_defectuosa": 10,
      "motivo_defecto": "danado",         // obligatorio si hay defectuosos
      "accion_defecto": "devolucion",     // obligatorio si hay defectuosos
      "fotos_evidencia_keys": ["originales/evidencia/abc123.jpg"]
    }
  ]
}
```

- Es un **evento inmutable**: se crea una vez, no se edita ni se borra (igual
  que una devolución de venta). Si te equivocaste, registrá otra recepción
  que lo corrija — el historial queda completo.
- `motivo_defecto`/`accion_defecto` van **juntos**: si `cantidad_defectuosa >
  0` son obligatorios (400 `DefectoInvalido` si faltan); si no hay
  defectuosos, no se mandan (400 si los mandás igual).
- `accion_defecto`:
  - `"merma"` → esa cantidad se da de baja del inventario ahí mismo (genera un
    movimiento `MERMA`, no vendible, se pierde).
  - `"devolucion"` → no toca inventario todavía; queda pendiente hasta que se
    cree una `DevolucionProveedor` (Parte 5) por esa cantidad.
  - `"aceptado_con_descuento"` → se vende igual con el defecto: se registra
    como si fuera bueno (no hay ajuste de precio automático — eso se negocia
    aparte con el proveedor).
- El **estado de la recepción** lo calcula el backend solo, no lo mandás:
  `con_defectos` si algo vino defectuoso, si no `parcial` si alguna línea con
  `cantidad_esperada` no llegó completa, si no `completa`.
- `fotos_evidencia_keys` son **keys de archivos ya subidos** (por el subidor de
  imágenes genérico que ya existe) — este endpoint no sube archivos, sólo
  guarda las referencias.

### Qué pasa en inventario (automático, misma transacción)

- Cada línea con `cantidad_recibida_buena > 0` genera una **ENTRADA** real de
  stock (el mismo mecanismo que `POST /movimientos`, con
  `referencia_tipo=recepcion_proveedor`).
- Cada línea con `cantidad_defectuosa > 0` y `accion_defecto=merma` genera una
  **MERMA** real (sale del stock, no es vendible).
- Si algo de esto falla (ej. el producto no admite stock negativo en algún
  caso raro), **toda la recepción se revierte** — un request es una
  transacción, no queda una recepción a medias.
- Si `pedido_id` viene, se suma lo bueno a `cantidad_recibida` de cada línea
  del pedido y se recalcula su estado (`parcial`/`recibido`).

Permiso: `recepcion_proveedor.registrar` (escritura), `recepcion_proveedor.
leer` (consulta). Listado: `GET /api/v1/recepciones-proveedor?proveedor_id=&sucursal_id=&pedido_id=`.

---

## Parte 5 — Devoluciones a proveedor

```
POST /api/v1/devoluciones-proveedor
{
  "proveedor_id": "…",
  "recepcion_id": "…",
  "lineas": [{ "recepcion_detalle_id": "…", "cantidad": 10 }]
}
```

- `recepcion_detalle_id` apunta a una línea concreta de una recepción. No
  podés devolver más de lo que esa línea marcó como `cantidad_defectuosa`
  (sumando lo que **ya** se haya devuelto de esa misma línea en devoluciones
  anteriores) — 400 `CantidadDevolucionExcedeDefecto` si te pasás.
- Ciclo de vida (3 estados, separado del resultado):

```
pendiente ──enviar──▶ enviada ──cerrar──▶ cerrada
```

```
POST /api/v1/devoluciones-proveedor/{id}/enviar
POST /api/v1/devoluciones-proveedor/{id}/cerrar
{ "resultado": "aceptada_proveedor", "tipo_resolucion": "nota_credito" }
```

- `resultado` (`aceptada_proveedor` / `rechazada_proveedor`) se fija recién al
  **cerrar**, no antes.
- `tipo_resolucion` (`reemplazo` / `nota_credito` / `reembolso`) es
  obligatorio sólo si `resultado = aceptada_proveedor`; si es rechazada, se
  ignora/limpia.
- No hay ajuste de inventario acá: lo defectuoso **nunca** había entrado al
  stock vendible (Parte 4), así que devolverlo no le saca nada al inventario.

Permiso: `devolucion_proveedor.gestionar` (escritura), `devolucion_proveedor.
leer` (consulta). Listado: `GET /api/v1/devoluciones-proveedor?proveedor_id=&estado=`.

---

## Parte 6 — Reporte por proveedor

```
GET /api/v1/proveedores/{id}/resumen
```

```json
{
  "total_unidades_recibidas": 100,
  "total_unidades_defectuosas": 10,
  "pct_defectuoso": 10.00,
  "tiempo_entrega_prometido_dias": 3.00,
  "tiempo_entrega_real_promedio_dias": 4.50,
  "devoluciones_pendientes": 1,
  "devoluciones_aceptadas": 2,
  "devoluciones_rechazadas": 1
}
```

- `tiempo_entrega_prometido_dias` = promedio de `tiempo_entrega_dias` de los
  vínculos `producto_proveedor` activos de ese proveedor.
- `tiempo_entrega_real_promedio_dias` = promedio real
  (`recepcion.fecha_recepcion − pedido.fecha_pedido`) de las recepciones que
  vinieron con `pedido_id`. Una recepción sin pedido (mercancía que llegó sin
  orden de compra previa) no entra en este promedio.
- `devoluciones_pendientes` cuenta `pendiente` + `enviada` (todavía sin
  cerrar); `aceptadas`/`rechazadas` sólo las ya `cerrada`.

Permiso: `proveedores.leer`.

---

## Parte 7 — Permisos

| Permiso | Para qué | Roles por defecto |
|---|---|---|
| `proveedores.leer` | Ver/listar proveedores, su catálogo de productos y su resumen | admin, gerente, almacenista |
| `proveedores.crear` | Dar de alta proveedores | admin, gerente |
| `proveedores.editar` | Editar/(des)activar proveedores | admin, gerente |
| `producto_proveedor.gestionar` | Vincular/desvincular productos, marcar principal | admin, gerente, almacenista |
| `pedido_proveedor.leer` | Ver/listar pedidos a proveedor | admin, gerente, almacenista |
| `pedido_proveedor.gestionar` | Crear pedidos manuales, cancelar | admin, gerente, almacenista |
| `pedido_proveedor.generar_manual` | Disparar el motor de reorden | admin, gerente, almacenista |
| `pedido_proveedor.confirmar_envio` | Confirmar el envío (borrador → enviado) | **admin, gerente** (no almacenista) |
| `recepcion_proveedor.leer` | Ver/listar recepciones | admin, gerente, almacenista |
| `recepcion_proveedor.registrar` | Registrar la llegada de mercancía | admin, gerente, almacenista |
| `devolucion_proveedor.leer` | Ver/listar devoluciones | admin, gerente, almacenista |
| `devolucion_proveedor.gestionar` | Crear, enviar y cerrar devoluciones | admin, gerente, almacenista |

---

## Parte 8 — Errores y qué significan

| Código | Error | Qué pasó |
|---|---|---|
| 400 | `DiasCreditoRequerido` | `condiciones_pago=credito` sin `dias_credito` (> 0) |
| 400 | `PedidoProveedorSinLineas` | Un pedido llegó sin líneas |
| 400 | `PedidoNoEditable` | Agregar líneas a un pedido que no está en `borrador` |
| 400 | `TransicionPedidoProveedorInvalida` | Ej. confirmar envío dos veces, cancelar un pedido `recibido` |
| 400 | `RecepcionSinLineas` | Una recepción llegó sin líneas |
| 400 | `DefectoInvalido` | Hay `cantidad_defectuosa` sin `motivo_defecto`/`accion_defecto`, o al revés |
| 400 | `CantidadDevolucionExcedeDefecto` | Se pidió devolver más de lo defectuoso disponible en esa línea |
| 400 | `TransicionDevolucionInvalida` | Ej. cerrar una devolución que no está `enviada` |
| 409 | `CodigoProveedorEnUso` | Ya existe un proveedor activo con ese `codigo` |
| 409 | `ProductoProveedorYaExiste` | Ese producto ya tiene un vínculo activo con ese proveedor |
| 409 | `YaHayProveedorPrincipal` | Otro proveedor ya es el principal (activo) de ese producto |
| 404 | `ProveedorNoEncontrado` / `ProductoProveedorNoEncontrado` / `PedidoProveedorNoEncontrado` / `RecepcionProveedorNoEncontrada` / `DevolucionProveedorNoEncontrada` | El `id` no existe |
| 422 | (formato) | Falta un campo obligatorio o el tipo de dato es incorrecto |

---

## Parte 9 — Flujo completo de ejemplo

```
1.  POST /proveedores                                    → proveedor
2.  POST /inventario/productos/{id}/proveedores           → vínculo, es_proveedor_principal: true

3.  POST /proveedores/reorden/evaluar?sucursal_id=…       → detecta stock bajo, crea pedido "borrador"
4.  POST /pedidos-proveedor/{id}/confirmar-envio          → "enviado"

5.  POST /recepciones-proveedor                           → 90 buenas + 10 defectuosas (accion=devolucion)
    → inventario sube 90 unidades reales; pedido queda "parcial" (90/100)

6.  POST /devoluciones-proveedor                          → devuelve las 10 defectuosas
7.  POST /devoluciones-proveedor/{id}/enviar
8.  POST /devoluciones-proveedor/{id}/cerrar              → { resultado: "aceptada_proveedor", tipo_resolucion: "nota_credito" }

9.  GET /proveedores/{id}/resumen                         → 10% defectuoso, 1 devolución aceptada
```

---

## Parte 10 — Checklist para las pantallas

- [ ] **Catálogo de proveedores**: alta/edición, buscador por código/razón social/RFC
- [ ] **Ficha de producto**: sección "Proveedores" — lista de vínculos, marcar principal, editar `stock_minimo`/`cantidad_reorden`/`precio_compra`
- [ ] **Panel de reabasto**: botón "evaluar reorden" por sucursal → muestra los pedidos borrador generados/actualizados
- [ ] **Pedidos a proveedor**: lista con filtro por estado; detalle con líneas y `subtotal`; botón "confirmar envío" (sólo gerente/admin) y "cancelar"
- [ ] **Recepción de mercancía**: formulario por línea — cantidad buena, cantidad defectuosa (si > 0, pedir motivo + acción + fotos), factura/remisión/transportista
- [ ] **Devoluciones**: crear desde una recepción con defectuosos (elegir línea + cantidad ≤ disponible), enviar, cerrar con resultado
- [ ] **Ficha de proveedor**: pestaña de resumen (% defectuoso, tiempo de entrega real vs prometido, devoluciones)

---

## Fuera de alcance (por ahora)

- Sin job programado para el reorden — siempre es un disparo manual.
- El estado `confirmado` de `pedido_proveedor` existe en la base pero no tiene
  ninguna acción que lo alcance todavía (no hay flujo de "ack del proveedor").
- Sin subida de imágenes propia para `fotos_evidencia_keys` — recibe keys ya
  subidas por el flujo genérico de imágenes.
- Sin impuestos en el pedido a proveedor (sólo `precio_compra` neto por línea).
- El `folio` (`OC-…`, `REC-…`, `DEV-…`) es un identificador corto derivado del
  `id`, no un correlativo secuencial real.
- Reporte de Fase 5 acotado a lo descrito en la Parte 6 — sin dashboard ni
  exportación.
