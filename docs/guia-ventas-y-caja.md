# Guía: ventas y caja (para la app)

> Cómo implementar la pantalla de punto de venta (POS) y el arqueo de caja, con
> los llamados a la API y lo que hay que tener en cuenta.
> Ventas cuelgan de `/api/v1/ventas`, la caja de `/api/v1/caja-turnos`.

---

## La idea en dos minutos

- Para **vender** hay que tener un **turno de caja abierto**. Sin turno, la API
  rechaza la venta.
- El **turno** es "esta caja, este cajero, desde que abrió hasta que cierra".
  Al abrir se declara el **efectivo inicial**; al cerrar, el **efectivo contado**.
  El sistema calcula la **diferencia** (sobrante / faltante).
- Una **venta** son líneas (producto + cantidad + precio) + pagos (efectivo,
  tarjeta, transferencia, crédito). Si lo pagado no cubre el total, el resto
  queda como **crédito** del cliente (y hace falta un `cliente_id`).
- Las ventas **no se editan ni se borran**. Si algo salió mal, se **anula**
  (revierte stock y crédito, deja la venta en `cancelada`).
- Todo lo de una venta pasa en **una sola transacción**: si falla el descuento de
  stock o el límite de crédito, **no queda nada** registrado.

---

## Parte 1 — Caja (turnos)

### 1.1 Abrir turno

Al iniciar el día / la jornada del cajero:

```
POST /api/v1/caja-turnos/abrir
{ "saldo_inicial": 1500.00 }
```

- La **sucursal** sale del usuario autenticado (el usuario tiene que tener una
  sucursal asignada; si no → 400).
- Permiso: `ventas.crear`.
- Un cajero sólo puede tener **un turno abierto por sucursal**. Si ya tiene uno →
  409 `TurnoYaAbierto` (hay que cerrarlo antes).
- Si la sucursal está inactiva o tiene `permite_ventas = false` → 409
  `SucursalNoOperativa`.

Respuesta: el turno con su `id`. Guardalo: va en **cada venta** (`caja_turno_id`).

### 1.2 Ver el turno abierto

```
GET /api/v1/caja-turnos/actual
```

Devuelve el turno abierto del cajero en su sucursal, o **404** si no hay ninguno
(la app usa esto al entrar al POS: sin turno → mostrar "Abrir caja").

### 1.3 Arqueo / resumen del turno

```
GET /api/v1/caja-turnos/{turno_id}
```

```json
{
  "turno": { "…": "…" },
  "total_efectivo": 4200.00,     // pagos en EFECTIVO de las ventas NO canceladas del turno
  "cantidad_ventas": 37,
  "saldo_esperado": 5700.00      // saldo_inicial + total_efectivo
}
```

Sirve tanto para un turno abierto (ver cómo va) como cerrado (revisar el cierre).

> El arqueo **sólo mira el efectivo**. Tarjeta, transferencia y crédito **no**
> entran en `saldo_esperado` — esos montos no están físicamente en el cajón.

### 1.4 Cerrar turno

Al terminar la jornada, el cajero cuenta el efectivo del cajón y lo declara:

```
POST /api/v1/caja-turnos/{turno_id}/cerrar
{ "saldo_final_declarado": 5680.00 }
```

- `diferencia = saldo_final_declarado − saldo_esperado`
  (**positivo = sobrante**, **negativo = faltante**). Queda guardada en el turno.
- Sólo el **dueño del turno** puede cerrarlo. `admin` / `gerente` (roles
  globales) pueden cerrar turnos de otros cajeros.
- Si ya está cerrado → 409 `TurnoYaCerrado`.

---

## Parte 2 — Ventas

### 2.1 Registrar una venta

```
POST /api/v1/ventas/
Idempotency-Key: <uuid opcional>      ← ver 2.5
{
  "caja_turno_id": "…",
  "cliente_id": null,                 // requerido sólo si queda saldo a crédito
  "descuento_total": 0,
  "lineas": [
    {
      "producto_id": "…",
      "cantidad": 2,
      "precio_unitario": 18.00,
      "descuento_linea": 0,
      "impuesto_tasa": 16,
      "producto_unidad_id": null      // null = unidad base; si viene, se vende esa presentación
    }
  ],
  "pagos": [
    { "monto": 36.00, "metodo_pago": "efectivo" }
  ]
}
```

Permiso: `ventas.crear`. La **sucursal** sale del usuario autenticado.

**Métodos de pago:** `efectivo`, `tarjeta_credito`, `tarjeta_debito`,
`transferencia`, `credito`.

### 2.2 Cómo se calcula el total

```
subtotal_linea = cantidad × precio_unitario − descuento_linea
total          = Σ subtotal_linea − descuento_total
saldo_pendiente = total − Σ pagos
```

- **El `impuesto_tasa` NO se suma al total.** Se guarda por línea como dato
  (para reportes / factura), pero el total que cobra el POS es el de arriba. Si
  necesitás mostrar IVA desglosado, lo calcula la app. (`precio_incluye_impuesto`
  del producto te dice si el precio ya lo trae adentro.)
- `descuento_linea` y `descuento_total` son dos niveles distintos: uno por
  renglón, otro sobre el total de la venta.

### 2.3 Pago completo vs. crédito

| `saldo_pendiente` | Qué pasa |
|---|---|
| `≤ 0` | Venta **`pagada`**. |
| `> 0` | Venta a **crédito**: requiere `cliente_id` (si no → 400 `VentaCreditoSinCliente`). Se valida el **límite de crédito** del cliente en el mismo commit; si no alcanza → 400 `LimiteCreditoExcedido` y **la venta entera falla**. Si pasa: estado **`pendiente_pago`** y se suma `saldo_pendiente` a la deuda del cliente. |

### 2.4 Qué hace la venta con el inventario

Todo dentro de la misma transacción que la venta. Por cada línea:

- **servicio** → no toca inventario.
- **kit** → explota la receta y descuenta cada componente.
- **producto con envase abierto** (`rastrea_instancia_abierta`) vendido **a
  granel** → consume de los envases abiertos (el más viejo primero) y abre uno
  nuevo si falta.
- **producto con lote** → descuenta por **FEFO** (vence primero). Puede repartir
  una línea entre varios lotes.
- resto → SALIDA en unidad base.
- Si una línea deja stock negativo y el producto no lo permite → 400
  `StockInsuficiente` y **se revierte toda la venta** (nada queda guardado).

**Mayoreo:** si la línea es por unidad base y `cantidad ≥ cantidad_minima_mayoreo`
del producto, el backend **usa `precio_mayoreo`** aunque el POS haya mandado otro
`precio_unitario`, y lo congela en la venta.

**Precios congelados:** `precio_unitario` e `impuesto_tasa` quedan fijos en
`detalle_venta`. Si después cambia el precio del producto en el catálogo, las
ventas viejas **no** se recalculan.

### 2.5 Idempotencia (evitar la venta doble)

Mandá un header `Idempotency-Key` (un UUID que genera la app por cada intento de
"cobrar"). Si el request se reintenta (timeout, doble tap), la API devuelve **la
misma venta** en vez de crear otra. Sin el header no hay protección: dos POST =
dos ventas.

### 2.6 Listar y ver ventas

```
GET /api/v1/ventas/?sucursal_id=&caja_turno_id=&cliente_id=&estado=&desde=&hasta=
    &page=1&page_size=20&sort=created_at:desc&include=cliente,usuario,caja_turno
GET /api/v1/ventas/{venta_id}?include=cliente,usuario,caja_turno
```

Permiso: `ventas.leer`. Un usuario con rol **de sucursal** sólo ve las de su
sucursal (aunque pida otra). `estado` ∈ `pagada` · `pendiente_pago` · `cancelada`.

### 2.7 Anular una venta

```
PATCH /api/v1/ventas/{venta_id}/anular
{ "motivo": "cobro duplicado" }
```

Permiso: `ventas.anular`. Efecto (todo en una transacción):

1. Revierte el **stock** de cada línea (ENTRADA inversa al mismo lote y sucursal;
   repone el envase abierto si la línea salió de uno).
2. Revierte el **crédito** consumido, si la venta tenía saldo a crédito.
3. Deja la venta en estado **`cancelada`** (no se borra: la tabla es append-only).

**Quién puede:**

- **Cajero**: sólo **sus** ventas y **mientras su turno siga abierto**.
- **admin / gerente**: cualquier venta, incluso de turnos ya cerrados.

Si ya estaba cancelada → 409 `VentaYaCancelada`.

> Anular una venta de un turno **cerrado** descuadra el arqueo que ya se hizo de
> ese turno. Por eso sólo lo permite un rol global.

---

## Parte 3 — Cosas a considerar al implementar

| Tema | Qué tener en cuenta |
|---|---|
| **Turno obligatorio** | El POS debe chequear `GET /caja-turnos/actual` al entrar. Sin turno → pantalla "Abrir caja", no dejar vender. |
| **Impuesto** | El backend **no** lo suma al total. Factura con IVA desglosado = cálculo del front (o pedir esa lógica al backend). |
| **Sin edición** | No hay "editar venta". Corrección = anular + volver a cobrar. La UI no debería ofrecer "modificar". |
| **Idempotencia** | Generá `Idempotency-Key` por operación de cobro y reusala en los reintentos. Nunca reintentar un POST de venta sin ella. |
| **Un turno por cajero** | Si el cajero cambia de caja física o de sucursal, cerrar y abrir. La app no debería permitir "abrir otro" sin cerrar. |
| **Arqueo = sólo efectivo** | Mostrar en el cierre: efectivo esperado (inicial + ventas efectivo), efectivo contado, diferencia. Tarjeta/transferencia se concilian aparte. |
| **Crédito atómico** | Venta a crédito que excede el límite → falla completa, no parcial. Mostrar el error `LimiteCreditoExcedido` con claridad. |
| **Stock atómico** | Si una línea no tiene stock, **toda** la venta se cae. Validar disponibilidad antes de cobrar (con el catálogo) reduce sorpresas, pero la verdad la tiene el POST. |
| **Presentaciones** | Vender "1 reja" = `producto_unidad_id` de la reja + `cantidad: 1`. El backend convierte a unidad base para el stock. El `precio_unitario` es el de **la reja**. |
| **Mayoreo** | Sólo aplica a líneas por unidad base. Si el POS ya muestra el precio de mayoreo, igual mandalo: el backend lo revalida y fuerza. |
| **Concurrencia** | Dos ventas simultáneas del mismo producto se protegen por transacción + chequeo de stock, pero no hay lock explícito. Si el volumen lo pide, agregar `SELECT … FOR UPDATE` sobre `existencia`. |
| **Devoluciones parciales** | Los estados `devuelta_parcial` / `devuelta_total` existen en el enum pero **no hay endpoint**. Hoy sólo se anula la venta completa. |
| **Permisos** | `ventas.crear` cubre vender **y** abrir/cerrar turno (no hay permiso propio de caja). `ventas.leer` para consultas, `ventas.anular` para anular. |

---

## Parte 4 — Flujos completos

### 4.1 Jornada de un cajero

1. Login → `GET /caja-turnos/actual`.
2. Si 404 → `POST /caja-turnos/abrir` con el efectivo del cajón.
3. Vender: N × `POST /ventas/` (cada una con `caja_turno_id` y su `Idempotency-Key`).
4. Durante el turno, para revisar: `GET /caja-turnos/{id}`.
5. Fin de jornada → contar efectivo → `POST /caja-turnos/{id}/cerrar`.
6. Mostrar la `diferencia` del cierre.

### 4.2 Venta al contado (efectivo)

```
POST /ventas/  { caja_turno_id, lineas:[…], pagos:[{monto: total, metodo_pago:"efectivo"}] }
→ estado "pagada"
```

### 4.3 Venta mixta (parte tarjeta, parte efectivo)

```
pagos: [
  { monto: 200, metodo_pago: "tarjeta_debito" },
  { monto:  50, metodo_pago: "efectivo" }
]
```
Si `200 + 50 == total` → `pagada`. En el arqueo del turno sólo cuentan los 50.

### 4.4 Venta a crédito (fía)

```
POST /ventas/  { caja_turno_id, cliente_id: "<obligatorio>", lineas:[…], pagos: [] }
→ total > 0 pagado, saldo_pendiente = total → estado "pendiente_pago"
→ el cliente queda debiendo `total` (validado contra su límite)
```
El pago posterior de esa deuda se maneja desde el módulo `clientes` (no crea otra venta).

### 4.5 Anular

```
PATCH /ventas/{id}/anular  { motivo: "…" }
→ stock repuesto, crédito devuelto, estado "cancelada"
```

---

## Parte 5 — Errores y qué significan

| Código | Error | Qué pasó |
|---|---|---|
| 400 | `CajaNoAbierta` | El `caja_turno_id` no corresponde a un turno abierto |
| 400 | `TurnoDeOtraSucursal` | El turno no es de la sucursal del usuario |
| 400 | `VentaSinLineas` | La venta llegó sin líneas |
| 400 | `VentaCreditoSinCliente` | Queda saldo pendiente y no mandaste `cliente_id` |
| 400 | `LimiteCreditoExcedido` | La deuda resultante supera el límite del cliente |
| 400 | `StockInsuficiente` | Una línea dejaría stock negativo (venta revertida entera) |
| 400 | "El usuario no tiene una sucursal asignada" | El cajero no tiene `sucursal_id` |
| 403 | `AnulacionNoPermitida` | Cajero anulando una venta ajena o de un turno cerrado |
| 403 | `CierreTurnoNoPermitido` | Cerrando un turno de otro sin ser rol global |
| 403 | "Fuera del alcance de su sucursal" | Consultando/anulando datos de otra sucursal |
| 409 | `TurnoYaAbierto` | El cajero ya tiene un turno abierto |
| 409 | `TurnoYaCerrado` | Cerrando/operando un turno ya cerrado |
| 409 | `VentaYaCancelada` | Anulando una venta que ya estaba cancelada |
| 409 | `SucursalNoOperativa` | Sucursal inactiva o `permite_ventas = false` |
| 404 | `TurnoNoEncontrado` / `VentaNoEncontrada` | El `id` no existe |
| 422 | (formato) | Falta un campo o el tipo es incorrecto (`cantidad ≤ 0`, `monto ≤ 0`, método de pago inválido…) |

---

## Parte 6 — Checklist para la pantalla POS

- [ ] Al entrar: `GET /caja-turnos/actual`; sin turno → bloquear venta, ofrecer "Abrir caja"
- [ ] **Abrir caja**: input `saldo_inicial`
- [ ] **Vender**: buscador de productos (por código de barras usa
      `GET /inventario/productos/resolver-codigo`), carrito con cantidad y precio,
      descuento por línea y total, selección de presentación
- [ ] **Pagos**: uno o varios, con método; mostrar `saldo_pendiente` en vivo
- [ ] Si queda saldo > 0: exigir seleccionar **cliente** antes de cobrar
- [ ] Generar y enviar **`Idempotency-Key`** en el POST de venta; reusarla en reintentos
- [ ] Manejar `StockInsuficiente` / `LimiteCreditoExcedido` sin perder el carrito
- [ ] Ticket / comprobante con el `id` de la venta que devuelve la API
- [ ] **Historial**: lista de ventas del turno (`?caja_turno_id=`), acción "Anular" (con `motivo`)
- [ ] **Cerrar caja**: mostrar `saldo_esperado`, input `saldo_final_declarado`, mostrar `diferencia`
- [ ] Roles: ocultar "Anular ventas viejas" y "Cerrar turno ajeno" si no es admin/gerente
