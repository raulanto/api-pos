# Guía: ventas y caja (para la app)

> Cómo implementar la pantalla de punto de venta (POS) y el arqueo de caja, con
> los llamados a la API y lo que hay que tener en cuenta.
> Ventas cuelgan de `/api/v1/ventas`, los turnos de `/api/v1/caja-turnos` y las
> cajas físicas (terminales) de `/api/v1/cajas`.

---

## La idea en dos minutos

- Para **vender** hay que tener un **turno de caja abierto**. Sin turno, la API
  rechaza la venta.
- Una **caja** (terminal física) pertenece a una sucursal. El **turno** es "esta
  caja, este cajero, desde que abrió hasta que cierra". Al abrir se declara el
  **efectivo inicial**; al cerrar, el **efectivo contado**. El sistema calcula la
  **diferencia** (sobrante / faltante); si supera un umbral, el turno queda
  `cerrado_con_diferencia` y necesita que un gerente lo **concilie**.
- Durante el turno se pueden registrar **movimientos de caja**: `retiro` (sale
  efectivo a caja fuerte), `ingreso` (refuerzo de fondo) y `gasto` (se paga algo
  del cajón). Cambian el efectivo esperado del arqueo.
- Una **venta** son líneas (producto + cantidad + precio) + pagos (efectivo,
  tarjeta, transferencia, crédito). Si lo pagado no cubre el total, el resto
  queda como **crédito** del cliente (y hace falta un `cliente_id`).
- Los **descuentos por promoción** (2x1, %, precio fijo por presentación) los
  aplica **solo el backend**: evalúa las promos vigentes de la sucursal y resta
  por línea. El POS puede pedir `POST /ventas/cotizar` para ver el total con
  todo aplicado **antes** de cobrar.
- Las ventas **no se editan ni se borran**. Si algo salió mal, se **anula**
  (revierte todo, deja la venta en `cancelada`); si el cliente devuelve **parte**
  de lo comprado, se hace una **devolución** (`devuelta_parcial` / `devuelta_total`).
- Todo lo de una venta pasa en **una sola transacción**: si falla el descuento de
  stock o el límite de crédito, **no queda nada** registrado. El stock se bloquea
  al descontar, así que dos ventas del último ítem no lo dejan negativo.

---

## Parte 1 — Caja (terminales, turnos, movimientos, arqueo)

### 1.0 Cajas físicas (terminales)

Una **caja** es una terminal de la sucursal. Toda sucursal arranca con una
`Caja 1` (la crea la migración). Sólo hace falta gestionarlas si la sucursal
tiene más de una terminal simultánea.

```
POST   /api/v1/cajas            { "nombre": "Caja 2" }        # crear   (caja.administrar)
GET    /api/v1/cajas?incluir_inactivas=false                  # listar  (caja.operar)
PATCH  /api/v1/cajas/{caja_id}  { "nombre": "Caja mostrador" }# renombrar (caja.administrar)
DELETE /api/v1/cajas/{caja_id}                                # desactivar (caja.administrar)
PATCH  /api/v1/cajas/{caja_id}/reactivar                      # reactivar  (caja.administrar)
```

El `nombre` es único **entre cajas activas** de la sucursal (409 `NombreCajaEnUso`).

### 1.1 Abrir turno

Al iniciar la jornada del cajero, sobre una terminal:

```
POST /api/v1/caja-turnos/abrir
{
  "caja_id": "…",
  "saldo_inicial": 1500.00,
  "denominaciones": [                 // opcional; si viene, su suma debe = saldo_inicial
    { "valor": 500, "cantidad": 2 },
    { "valor": 100, "cantidad": 5 }
  ]
}
```

- La **sucursal** sale del usuario autenticado (si no tiene sucursal → 400).
- `caja_id` debe ser una caja **activa** de esa sucursal (si no → 404
  `CajaNoEncontrada` / 409 `CajaInactiva`).
- Permiso: `caja.operar` (o `ventas.crear`, que lo sigue habilitando).
- **Un turno abierto por terminal** y **un turno abierto por cajero**: si la caja
  ya tiene turno, o el cajero ya tiene uno (en cualquier terminal) → 409
  `TurnoYaAbierto`. Lo garantizan índices únicos en la BD.
- Si `denominaciones` no suma `saldo_inicial` → 400 `DenominacionNoCuadra`.
- Sucursal inactiva o `permite_ventas = false` → 409 `SucursalNoOperativa`.

Respuesta: el turno con su `id`. Guardalo: va en **cada venta** (`caja_turno_id`).

### 1.2 Ver el turno abierto

```
GET /api/v1/caja-turnos/actual
```

Devuelve el turno abierto del cajero en su sucursal, o **404** si no hay ninguno
(la app usa esto al entrar al POS: sin turno → mostrar "Abrir caja").

### 1.3 Movimientos de caja (retiro / ingreso / gasto)

Durante el turno, cuando entra o sale efectivo por algo que **no** es una venta:

```
POST /api/v1/caja-turnos/{turno_id}/movimientos
{ "tipo": "retiro", "monto": 2000.00, "motivo": "traslado a caja fuerte" }
```

```
GET  /api/v1/caja-turnos/{turno_id}/movimientos    # lista los del turno
```

- `tipo`: `retiro` (sale del cajón), `ingreso` (entra sin ser venta), `gasto`
  (se paga algo del cajón). `retiro` y `gasto` exigen `motivo` (400
  `MotivoMovimientoRequerido`); `monto` > 0.
- Sólo sobre un turno **abierto** (409 `MovimientoTurnoCerrado`). Permiso
  `caja.operar`; para operar un turno ajeno hace falta `caja.forzar_cierre`.
- Son **inmutables** (no se editan ni borran) y quedan en auditoría.
- Efecto en el arqueo: `+ ingresos − retiros − gastos`.

### 1.4 Arqueo / resumen del turno

```
GET /api/v1/caja-turnos/{turno_id}
```

```json
{
  "turno": { "…": "…" },
  "total_efectivo": 4200.00,
  "total_devoluciones_efectivo": 150.00,
  "cantidad_ventas": 37,
  "total_ingresos": 300.00,
  "total_retiros": 2000.00,
  "total_gastos": 120.00,
  "movimientos_neto": -1820.00,          // ingresos − retiros − gastos
  "saldo_esperado": 3730.00,             // saldo_inicial + total_efectivo − total_devoluciones_efectivo + movimientos_neto
  "denominaciones_apertura": [ … ],
  "denominaciones_cierre": [ … ]
}
```

Sirve tanto para un turno abierto (ver cómo va) como cerrado (revisar el cierre).

> El arqueo **sólo mira el efectivo**. Tarjeta, transferencia, crédito y monedero
> **no** entran en `saldo_esperado`. Las **devoluciones en efectivo** y los
> **retiros/gastos** lo bajan; los **ingresos** lo suben.

Para el **corte completo** (desglose por método de pago —incl. `total_monedero`—,
más `total_descuento_promo`, `total_devoluciones_efectivo`, `total_ingresos`,
`total_retiros` y `total_gastos`): `GET /api/v1/reportes/corte-caja/{turno_id}`
(permiso `reportes.leer`).

### 1.5 Cerrar turno

Al terminar la jornada, el cajero cuenta el efectivo del cajón y lo declara:

```
POST /api/v1/caja-turnos/{turno_id}/cerrar
{
  "saldo_final_declarado": 3680.00,
  "nota_cierre": "faltante de 50, se avisó a gerencia",   // obligatoria si |diferencia| >= umbral
  "denominaciones": [ … ]                                 // opcional; su suma debe = saldo_final_declarado
}
```

- `saldo_esperado = saldo_inicial + efectivo_de_ventas − devoluciones_en_efectivo`
  `+ ingresos − retiros − gastos` (movimientos de caja incluidos).
- `diferencia = saldo_final_declarado − saldo_esperado`
  (**positivo = sobrante**, **negativo = faltante**). Siempre queda guardada.
- Si `|diferencia|` supera el umbral (`CAJA_DIFERENCIA_UMBRAL`, por defecto
  `20.00`): hace falta `nota_cierre` (si no → 400 `NotaCierreRequerida`) y el
  turno queda en estado **`cerrado_con_diferencia`** (pendiente de conciliar). Si
  no lo supera, queda `cerrado`.
- Sólo el **dueño del turno** puede cerrarlo; con permiso `caja.forzar_cierre` se
  puede cerrar el de otro cajero (turno abandonado).
- Si ya está cerrado → 409 `TurnoYaCerrado`.

### 1.6 Conciliar un turno con diferencia

Un gerente/admin revisa y autoriza el turno `cerrado_con_diferencia`:

```
POST /api/v1/caja-turnos/{turno_id}/conciliar
{ "nota": "autorizado, se descuenta de caja chica" }
```

- Permiso `caja.autorizar_diferencia` (si no → 403 `ConciliacionNoPermitida`).
- El turno pasa a **`conciliado`** y guarda `conciliado_por` / `conciliado_en`.
- Si el turno no está `cerrado_con_diferencia` → 409 `TurnoNoRequiereConciliacion`.

### 1.7 Histórico y efectivo en tiempo real

```
GET /api/v1/caja-turnos/historico?sucursal_id=&caja_id=&usuario_id=&estado=&desde=&hasta=
    &page=1&page_size=20&sort=abierto_en:desc
GET /api/v1/caja-turnos/efectivo-actual?sucursal_id=
```

- `historico`: lista de turnos con su `diferencia` (filtrar por `usuario_id` da
  las diferencias por cajero). Permiso `caja.ver_historico`.
- `efectivo-actual`: suma del `saldo_esperado` de los turnos **abiertos** de la
  sucursal (efectivo que debería haber en los cajones ahora). Permiso
  `caja.ver_historico`.

---

## Parte 2 — Ventas

### 2.0 Catálogo de productos para el POS

No hay endpoint propio de "productos para vender": el buscador del POS usa el de
inventario con este preset.

```
GET /api/v1/inventario/productos
    ?activo=true
    &sucursal_id=<suc del cajero>        // sólo productos con existencia ahí
    &q=<texto>                           // busca en nombre, sku y código de barras
    &include=unidades,existencias
    &page=1&page_size=50
```

Permiso `inventario.leer` (el rol `cajero` ya lo tiene). Devuelve cada producto
con:

- `precio_venta`, `impuesto_tasa`, `precio_incluye_impuesto`, `tipo`,
  `permite_venta_fraccionada`, `incremento_minimo_venta`, `precio_mayoreo` /
  `cantidad_minima_mayoreo`.
- `imagen_principal` (portada del producto, prefirmada).
- `unidades[]`: las presentaciones (reja, six-pack…), cada una con su `id`
  (`producto_unidad_id` para la línea de venta), `factor`, `precio_venta`,
  `codigo_barras` y su propia `imagen_principal`.
- `existencias[]`: stock por sucursal (acotado a `sucursal_id`).

**Escaneo de código de barras:** `GET /api/v1/inventario/productos/buscar?codigo_barras=…`
(producto) y `GET /api/v1/inventario/productos/resolver-codigo?codigo_barras=…`
(resuelve si el código es de una presentación y te da `unidad_id` + `factor` +
`precio_venta`). Ambos con permiso `inventario.leer`.

**Precio final** (con mayoreo y promociones aplicados según la cantidad): no lo
da el catálogo, lo da `POST /ventas/cotizar` (ver 2.4).

### 2.1 Registrar una venta

```
POST /api/v1/ventas/
Idempotency-Key: <uuid opcional>      ← ver 2.7
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
    { "monto": 36.00, "metodo_pago": "efectivo", "monto_recibido": 50.00 }
  ]
}
```

Permiso: `ventas.crear`. La **sucursal** sale del usuario autenticado.

> **`monto_recibido`** es opcional y sólo tiene sentido en efectivo: con cuánto
> pagó el cliente. Si viene, debe ser ≥ `monto`. El backend guarda el **cambio**
> (`monto_recibido − monto`) por pago; en la venta quedan `efectivo_recibido` y
> `cambio` totales, y salen en el ticket. El `monto` que se aplica a la venta no
> cambia (el cambio vuelve al cliente, no queda en el cajón → el arqueo no se toca).

**Métodos de pago:** `efectivo`, `tarjeta_credito`, `tarjeta_debito`,
`transferencia`, `credito`, `monedero` (ver 2.12).

> **`telefono`** (opcional, string): registra la compra para el **historial por
> teléfono** (`GET /ventas/?telefono=…`) y habilita el **monedero** (cashback).
> **No** obliga a registrar un `cliente` ni tiene nada que ver con el crédito.
> Es obligatorio sólo si algún pago usa `metodo_pago="monedero"`.

> **`codigo_cupon`** (opcional): habilita una promoción que exige cupón. **`motivo_descuento`**
> (opcional): **obligatorio** si mandás `descuento_linea` o `descuento_total` > 0
> (ver 2.13). Detalle completo de promos, cupones y descuento manual en
> **`docs/guia-promociones.md`**.

### 2.2 Cómo se calcula el total

```
subtotal_linea = cantidad × precio_unitario − descuento_linea − promo_descuento
total          = Σ subtotal_linea − descuento_total
saldo_pendiente = total − Σ pagos
```

- **El `impuesto_tasa` NO se suma al total.** Se guarda por línea como dato
  (para reportes / factura), pero el total que cobra el POS es el de arriba. Si
  necesitás mostrar IVA desglosado, lo calcula la app. (`precio_incluye_impuesto`
  del producto te dice si el precio ya lo trae adentro.)
- `descuento_linea` (lo manda el POS) y `descuento_total` (sobre el total) son
  dos niveles de descuento **manual**. `promo_descuento` es aparte: lo calcula el
  motor de **promociones** (ver 2.3) y viene ya en la respuesta, junto con
  `promo_etiqueta` por línea y `total_promociones` en la venta.

### 2.3 Promociones y mayoreo

Dos formas de que el precio final sea menor al de catálogo, **las dos las decide
el backend** (el POS manda el precio de lista y el backend lo revalida):

**Mayoreo simple (`precio_mayoreo` del producto).** Sólo en líneas **por unidad
base**: si `cantidad ≥ cantidad_minima_mayoreo`, usa `precio_mayoreo` en vez de
`precio_unitario` y lo congela en la venta. Las presentaciones (la reja) no lo
usan.

**Promociones (módulo aparte, `/api/v1/promociones`).** Reglas configurables que
apuntan a productos, presentaciones o **categorías**. Tipos: `nxm` (2x1, 3x2…),
`porcentaje`, `precio_fijo`. Al vender:

- El backend filtra las promos **vigentes** para la venta —activas, ventana de
  fechas, **día de la semana y hora local**, sucursal, **monto mínimo de
  compra**, **método de pago** presente en los pagos, **segmento del cliente**, y
  cupón si la promo lo exige— y calcula el descuento por línea. Lo congela en
  `detalle_venta.promo_descuento` (+ el desglose en `promos_aplicadas`).
- **Apilado:** por defecto una promo es **exclusiva** (una por línea, gana la de
  `prioridad` menor). Si la promo es `combinable`, se apila **sobre el precio ya
  descontado** junto a otras combinables, respetando su `tope_descuento`.
- **Cupón:** las promos `requiere_cupon` sólo aplican si la venta manda un
  `codigo_cupon` válido (vigencia + límite de usos; ver 2.12).
- **NxM** junta las unidades enteras de todas las líneas del mismo objetivo y
  regala las más baratas. Ignora cantidades con decimales.
- Corre **después** del mayoreo simple (`precio_mayoreo` fija el precio, la promo
  se calcula encima). El motor es **defensivo**: una promo mal configurada
  simplemente no aplica.

Cómo se dan de alta las promos, los cupones y el descuento manual del POS:
**`docs/guia-promociones.md`**.

### 2.4 Previsualizar el total antes de cobrar (cotizar)

```
POST /api/v1/ventas/cotizar
{
  "descuento_total": 0,
  "lineas": [ { "producto_id": "…", "cantidad": 6, "precio_unitario": 30,
               "producto_unidad_id": null } ]
}
```

Corre el **mismo cálculo de precios** que la venta real —mayoreo + promociones +
conversión a unidad base (que valida que el producto y la presentación
existan)— pero **no** exige turno, **no** pide pagos, **no** toca stock y **no**
guarda nada. Permiso `ventas.crear`; la sucursal sale del usuario.

Respuesta:

```json
{
  "lineas": [
    {
      "producto_id": "…", "cantidad": 6, "precio_unitario": 30,
      "promo_id": "…", "promo_etiqueta": "3x2 Refresco",
      "promo_descuento": 60.00, "subtotal": 120.00,
      "cantidad_en_unidad_base": 6,
      "stock_disponible": 40, "hay_stock": true
    }
  ],
  "descuento_total": 0,
  "total_promociones": 60.00,
  "total": 120.00
}
```

- `stock_disponible` está en la **unidad de la línea** (si pediste una
  presentación, en esa presentación); `null` = ilimitado (servicio, sobre pedido,
  kit sin receta). `hay_stock` = `stock_disponible >= cantidad`.
- Úsalo en cada cambio del carrito para mostrar "promo aplicada", el total real y
  avisar de líneas sin stock.
- **Ojo:** cotizar **no reserva** stock. Entre cotizar y cobrar otro puede llevarse
  la última unidad → la venta falla con `StockInsuficiente`.

### 2.5 Pago completo vs. crédito

| `saldo_pendiente` | Qué pasa |
|---|---|
| `≤ 0` | Venta **`pagada`**. |
| `> 0` | Venta a **crédito**: requiere `cliente_id` (si no → 400 `VentaCreditoSinCliente`). Se valida el **límite de crédito** del cliente en el mismo commit; si no alcanza → 400 `LimiteCreditoExcedido` y **la venta entera falla**. Si pasa: estado **`pendiente_pago`** y se suma `saldo_pendiente` a la deuda del cliente. |

### 2.6 Qué hace la venta con el inventario

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

**Precios congelados:** `precio_unitario`, `impuesto_tasa`, `promo_descuento` y
`promo_etiqueta` quedan fijos en `detalle_venta`. Si después cambia el precio del
producto o se apaga la promo, las ventas viejas **no** se recalculan.

### 2.7 Idempotencia (evitar la venta doble)

Mandá un header `Idempotency-Key` (un UUID que genera la app por cada intento de
"cobrar"). Si el request se reintenta (timeout, doble tap), la API devuelve **la
misma venta** en vez de crear otra. Sin el header no hay protección: dos POST =
dos ventas.

### 2.8 Listar y ver ventas

```
GET /api/v1/ventas/?sucursal_id=&caja_turno_id=&cliente_id=&estado=&desde=&hasta=
    &page=1&page_size=20&sort=created_at:desc&include=cliente,usuario,caja_turno
GET /api/v1/ventas/{venta_id}?include=cliente,usuario,caja_turno
```

Permiso: `ventas.leer`. Un usuario con rol **de sucursal** sólo ve las de su
sucursal (aunque pida otra). `estado` ∈ `pagada` · `pendiente_pago` · `cancelada`
· `devuelta_parcial` · `devuelta_total`.

Cada venta trae `total_promociones` (suma de `promo_descuento` de sus líneas) y
cada línea `promo_descuento` + `promo_etiqueta`, para el ticket ("Ahorraste $X").
El reporte del período con el total de descuentos por promo:
`GET /api/v1/reportes/ventas` → campo `total_descuento_promo`.

### 2.9 Anular una venta

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

Si ya estaba cancelada → 409 `VentaYaCancelada`. Si la venta tiene
**devoluciones** registradas → 403 `AnulacionNoPermitida` (ya se repuso stock
parcial; hay que devolver el resto con el endpoint de devolución, no anular).

> Anular una venta de un turno **cerrado** descuadra el arqueo que ya se hizo de
> ese turno. Por eso sólo lo permite un rol global.

### 2.10 Devolución parcial o total

Cuando el cliente trae de vuelta parte (o todo) de lo que compró — sin anular la
venta entera:

```
POST /api/v1/ventas/{venta_id}/devolucion
Idempotency-Key: <uuid opcional>
{
  "caja_turno_id": "…",                 // el turno EN QUE se hace la devolución
  "metodo_devolucion": "efectivo",      // efectivo | tarjeta | credito
  "motivo": "producto fallado",
  "lineas": [
    { "detalle_venta_id": "…", "cantidad": 2 }
  ]
}
```

Permiso `ventas.devolver`. Efecto (una sola transacción):

1. **Stock**: ENTRADA de lo devuelto, al mismo lote del que salió (repartido por
   los movimientos de la venta). Un servicio no toca stock; un kit se explota.
2. **Dinero**: `monto_devuelto` = subtotal neto de cada línea (con su
   `descuento_linea` y `promo_descuento`) prorrateado por la cantidad devuelta.
   - `metodo_devolucion: "credito"` → baja la deuda del cliente.
   - `"efectivo"` → sale plata del cajón: **descuenta del arqueo** del turno.
   - `"tarjeta"` → reverso a la tarjeta, no toca el cajón.
3. Sube `detalle_venta.cantidad_devuelta` de cada línea y recalcula el estado de
   la venta: **`devuelta_parcial`** si queda algo por devolver, **`devuelta_total`**
   si ya no.

**Reglas:**

- No se puede devolver una venta `cancelada` ni una ya `devuelta_total` → 400
  `VentaNoDevolvible`.
- No se puede devolver más de `cantidad − cantidad_devuelta` de una línea → 400
  `CantidadDevolucionExcedida`.
- **Cajero**: sólo en su turno abierto. **admin / gerente**: turnos cerrados / ajenos.
- `Idempotency-Key` repetida → devuelve la misma devolución, sin reponer dos veces.

`GET /api/v1/ventas/{venta_id}/devoluciones` lista las devoluciones de una venta.
`GET /api/v1/ventas/{venta_id}` trae `total_devuelto` y `cantidad_devuelta` por línea.

### 2.11 Ticket en PDF

```
GET /api/v1/ventas/{venta_id}/ticket
```

Devuelve el ticket como **`application/pdf`** (`Content-Disposition: inline`, ancho
~80 mm, listo para impresora térmica). Permiso `ventas.leer`; alcance por sucursal.
La app lo puede pintar directo (visor de PDF / `<embed>` / imprimir).

Incluye: sucursal (nombre, dirección, teléfono), folio + fecha, estado, cliente
(si es a crédito), líneas con cantidad × precio − descuento (y la etiqueta de la
promo), subtotal / promociones / total, y por cada pago el método, el **recibido**
y el **cambio**. Si la venta tiene saldo pendiente o devoluciones, también. Si hay
`telefono`, muestra el monedero **usado** y **acumulado**.

### 2.12 Monedero electrónico (cashback por teléfono)

Un **monedero** es un saldo asociado a un **teléfono** (tabla propia, no es un
`cliente`). Se llena solo con las compras y se puede gastar en compras futuras.

**Cómo se genera.** Cada producto / presentación puede configurar (en el módulo
de inventario) `monedero_pct` (% del subtotal de la línea) o `monedero_monto`
(fijo por unidad). Al vender **con `telefono`**, el backend suma lo que generó
cada línea y lo acredita al monedero de ese teléfono; lo congela en
`venta.monedero_generado`. La presentación, si tiene alguno de los dos, manda
sobre el del producto. `POST /ventas/cotizar` devuelve `monedero_a_generar` para
mostrarlo antes de cobrar. (Una venta a **crédito** también acumula al momento.)

**Cómo se gasta.** Un pago más en `pagos[]` con `metodo_pago:"monedero"`:

```
POST /api/v1/ventas/
{
  "caja_turno_id": "…",
  "telefono": "5550001234",            // obligatorio si se paga con monedero
  "lineas": [ … ],
  "pagos": [
    { "monto": 20.00, "metodo_pago": "monedero" },
    { "monto": 80.00, "metodo_pago": "efectivo" }
  ]
}
```

- El saldo se bloquea (`FOR UPDATE`) y se descuenta en la misma transacción. Si
  no alcanza → 400 `SaldoMonederoInsuficiente` y **la venta no se crea**.
- Sin `telefono` → 400 `MovimientoMonederoInvalido`.
- No es efectivo: **no** entra en el arqueo (`saldo_esperado`). En el corte de
  caja aparece como `total_monedero` aparte.
- En la venta quedan `monedero_usado` (Σ pagos monedero) y `monedero_generado`.

**Consultar / ajustar** (`/api/v1/clientes/monedero/...`):

| Método | Ruta | Permiso | Qué hace |
|---|---|---|---|
| GET | `/monedero/{telefono}` | `clientes.leer` | Saldo actual (404 si el teléfono no tiene monedero) |
| GET | `/monedero/{telefono}/movimientos` | `clientes.leer` | Ledger paginado (historial: acumulación / consumo / reversos / ajuste) |
| POST | `/monedero/{telefono}/ajustar` | `monedero.ajustar` | `{ monto: ±N, motivo }` — carga saldo inicial o corrige (crea la cuenta si no existe; no deja saldo negativo) |

**Anular / devolver.**

- **Anular** una venta con monedero revierte todo: quita lo acumulado (con tope
  al saldo actual, por si ya se gastó) y reintegra lo que se pagó con monedero.
- **Devolución** (2.10) acepta `metodo_devolucion:"monedero"` → reintegra
  `monto_devuelto` al monedero del teléfono de la venta. (No prorratea ni quita
  la acumulación que generó esa línea.)

### 2.13 Descuento manual (`descuento_linea` / `descuento_total`)

El descuento libre que teclea el cajero (por línea o sobre el total) es **aparte**
de las promociones. Al mandarlo en la venta:

- Requiere el permiso **`ventas.descuento_manual`** (por defecto `admin` /
  `gerente`). Sin él → 403 `DescuentoManualNoAutorizado`.
- Requiere **`motivo_descuento`** en el cuerpo → si no, 400
  `MotivoDescuentoRequerido`. Se congela en `venta.motivo_descuento`.
- Respeta un **tope de % por rol** (tabla `descuento_manual_limite`; `NULL` = sin
  tope). Si el % supera el tope → 400 `DescuentoManualExcedeTope`.
- Queda **auditado** (`GET /api/v1/auditoria`, acción `descuento_manual`).

Detalle y ejemplos: **`docs/guia-promociones.md`** (Parte 4).

---

## Parte 3 — Cosas a considerar al implementar

| Tema | Qué tener en cuenta |
|---|---|
| **Turno obligatorio** | El POS debe chequear `GET /caja-turnos/actual` al entrar. Sin turno → pantalla "Abrir caja", no dejar vender. |
| **Impuesto** | El backend **no** lo suma al total. Factura con IVA desglosado = cálculo del front (o pedir esa lógica al backend). |
| **Sin edición** | No hay "editar venta". Corrección = anular + volver a cobrar. La UI no debería ofrecer "modificar". |
| **Idempotencia** | Generá `Idempotency-Key` por operación de cobro y reusala en los reintentos. Nunca reintentar un POST de venta sin ella. |
| **Un turno por cajero y por caja** | El cajero abre sobre una `caja_id`. No puede tener dos turnos abiertos (ni en distintas terminales), ni abrir en una caja que ya tiene turno. Cambiar de terminal/sucursal = cerrar y abrir. |
| **Arqueo = sólo efectivo** | En el cierre: efectivo esperado (inicial + ventas efectivo + ingresos − retiros − gastos − devoluciones efectivo), efectivo contado, diferencia. Tarjeta/transferencia/monedero se concilian aparte. |
| **Movimientos de caja** | Retiro a caja fuerte, ingreso de fondo o gasto del cajón: `POST /caja-turnos/{id}/movimientos`. Son inmutables y ajustan el efectivo esperado. |
| **Diferencia grande = conciliación** | Si el cierre pasa el umbral (`CAJA_DIFERENCIA_UMBRAL`), el turno queda `cerrado_con_diferencia` con `nota_cierre` obligatoria y un gerente debe `POST /caja-turnos/{id}/conciliar` (`caja.autorizar_diferencia`). |
| **Crédito atómico** | Venta a crédito que excede el límite → falla completa, no parcial. Mostrar el error `LimiteCreditoExcedido` con claridad. |
| **Stock atómico** | Si una línea no tiene stock, **toda** la venta se cae con `StockInsuficiente`. `POST /ventas/cotizar` devuelve `stock_disponible` / `hay_stock` por línea para avisar antes de cobrar (no reserva). Manejar el error del POST sin vaciar el carrito. |
| **Presentaciones** | Vender "1 reja" = `producto_unidad_id` de la reja + `cantidad: 1`. El backend convierte a unidad base para el stock. El `precio_unitario` es el de **la reja**. |
| **Mayoreo** | Sólo aplica a líneas por unidad base. Si el POS ya muestra el precio de mayoreo, igual mandalo: el backend lo revalida y fuerza. |
| **Promociones** | Se aplican solas (backend); el POS no manda nada. Para mostrar "promo aplicada" y el total real en el carrito, pedí `POST /ventas/cotizar` cada vez que cambia. Lo que se cobró queda congelado (`promo_descuento` / `promo_etiqueta` por línea). |
| **Cotizar ≠ reservar** | `POST /ventas/cotizar` informa `stock_disponible` pero **no lo reserva**. Entre cotizar y cobrar, otro puede llevarse la última unidad. |
| **Concurrencia** | Al descontar stock el backend bloquea la fila (`SELECT … FOR UPDATE` sobre `existencia` / `existencia_lote`), así que dos ventas simultáneas del último ítem se serializan: una pasa, la otra da `StockInsuficiente`. Lo mismo el límite de crédito y "un turno abierto por cajero" (índice único). No hace falta que el front haga nada especial. |
| **Devoluciones** | `POST /ventas/{id}/devolucion` (parcial o total): repone stock, ajusta cajón/crédito, deja la venta `devuelta_parcial` / `devuelta_total`. Una venta con devoluciones ya **no** se puede anular. |
| **Monedero** | `telefono` en la venta habilita el cashback (config por producto/presentación) y el historial por teléfono; no exige `cliente` ni toca el crédito. Pagar con `metodo_pago:"monedero"` descuenta el saldo (bloqueado `FOR UPDATE`); no es efectivo → fuera del arqueo, va como `total_monedero` en el corte. Consulta/ajuste en `/api/v1/clientes/monedero/{telefono}`. |
| **Permisos** | `caja.operar` para abrir/cerrar turno, movimientos y arqueo (o `ventas.crear`, que lo sigue habilitando); `caja.administrar` para alta/baja de terminales; `caja.forzar_cierre` para cerrar/operar el turno de otro cajero; `caja.autorizar_diferencia` para conciliar; `caja.ver_historico` para el histórico y el efectivo en tiempo real. `ventas.crear` para vender, `ventas.leer` para consultas, `ventas.anular` para anular, `ventas.devolver` para devoluciones, `monedero.ajustar` para ajustar saldos de monedero. |

---

## Parte 4 — Flujos completos

### 4.1 Jornada de un cajero

1. Login → `GET /caja-turnos/actual`.
2. Si 404 → elegir terminal (`GET /cajas`) → `POST /caja-turnos/abrir`
   (`caja_id` + efectivo del cajón).
3. Armar carrito → (cada cambio) `POST /ventas/cotizar` para mostrar promos y total.
4. Cobrar: `POST /ventas/` (con `caja_turno_id` y su `Idempotency-Key`).
5. Retiro a caja fuerte / gasto del cajón → `POST /caja-turnos/{id}/movimientos`.
6. Durante el turno, para revisar: `GET /caja-turnos/{id}`.
7. Fin de jornada → contar efectivo → `POST /caja-turnos/{id}/cerrar` (con
   `nota_cierre` si la diferencia es grande).
8. Si quedó `cerrado_con_diferencia` → un gerente `POST /caja-turnos/{id}/conciliar`.

### 4.2 Venta al contado (efectivo)

```
POST /ventas/  { caja_turno_id, lineas:[…],
                 pagos:[{monto: total, metodo_pago:"efectivo", monto_recibido: 50}] }
→ estado "pagada" ; venta.cambio = 50 − total
GET /ventas/{id}/ticket → PDF para imprimir/mostrar
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

### 4.6 Venta con promoción (2x1)

```
1) POST /ventas/cotizar  { lineas:[{producto_id:X, cantidad:4, precio_unitario:25}] }
   → linea.promo_etiqueta "2x1 X", promo_descuento 50.00, total 50.00
2) POST /ventas/  { caja_turno_id, lineas:[…igual…], pagos:[{monto:50, metodo_pago:"efectivo"}] }
   → estado "pagada", total_promociones 50.00
```

El POS no configura nada: la promo "2x1 X" ya existe y está vigente para la sucursal.

### 4.7 Devolución parcial

```
1) POST /ventas/{id}/devolucion
   { caja_turno_id, metodo_devolucion:"efectivo", lineas:[{detalle_venta_id, cantidad:2}] }
   → devolucion.monto_devuelto = 2 × precio neto ; venta pasa a "devuelta_parcial"
   → stock +2 ; arqueo del turno baja ese efectivo
2) (más tarde) devolver el resto → venta "devuelta_total"
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
| 400 | `VentaNoDevolvible` | Devolución sobre una venta cancelada o ya `devuelta_total` |
| 400 | `CantidadDevolucionExcedida` | Pediste devolver más de lo que queda por devolver en esa línea |
| 400 | `DevolucionInvalida` | Línea que no es de la venta, cantidad ≤ 0, o sin líneas; o devolución al monedero de una venta sin `telefono` |
| 400 | `SaldoMonederoInsuficiente` | El monedero del teléfono no cubre el pago (venta revertida entera) |
| 400 | `MovimientoMonederoInvalido` | Pago con `metodo_pago="monedero"` sin `telefono`, o ajuste de monedero en 0 |
| 400 | `MotivoDescuentoRequerido` | Hay descuento manual (`descuento_linea`/`descuento_total`) sin `motivo_descuento` |
| 400 | `DescuentoManualExcedeTope` | El % de descuento manual supera el tope del rol |
| 400 | `CuponVencido` | El `codigo_cupon` está fuera de vigencia o desactivado (venta no creada) |
| 400 | `NotaCierreRequerida` | La diferencia del cierre (en valor absoluto) llega al umbral y no vino `nota_cierre` |
| 400 | `MotivoMovimientoRequerido` | Movimiento de caja `retiro` / `gasto` sin `motivo` |
| 400 | `DenominacionNoCuadra` | La suma del desglose por denominación ≠ saldo declarado |
| 403 | `DescuentoManualNoAutorizado` | Venta con descuento manual y el usuario no tiene `ventas.descuento_manual` |
| 403 | `AnulacionNoPermitida` | Cajero anulando/devolviendo una venta ajena o de un turno cerrado; o anulando una venta **con devoluciones** |
| 403 | `ConciliacionNoPermitida` | Conciliando un turno sin el permiso `caja.autorizar_diferencia` |
| 404 | `CuponNoEncontrado` | El `codigo_cupon` no existe |
| 404 | `CajaNoEncontrada` | La `caja_id` no existe o no es de la sucursal |
| 409 | `CuponAgotado` | El cupón llegó a su límite de usos (total o por persona) — venta no creada |
| 403 | `CierreTurnoNoPermitido` | Cerrando/operando un turno de otro sin `caja.forzar_cierre` |
| 403 | "Fuera del alcance de su sucursal" | Consultando/anulando datos de otra sucursal |
| 409 | `TurnoYaAbierto` | El cajero, o la caja, ya tiene un turno abierto (chequeo + índice único) |
| 409 | `TurnoYaCerrado` | Cerrando/operando un turno ya cerrado |
| 409 | `MovimientoTurnoCerrado` | Registrando un movimiento de caja en un turno no abierto |
| 409 | `TurnoNoRequiereConciliacion` | Conciliando un turno que no está `cerrado_con_diferencia` |
| 409 | `CajaInactiva` | Abriendo turno en una caja/terminal desactivada |
| 409 | `NombreCajaEnUso` | Alta/rename de caja con un nombre que ya usa otra caja activa |
| 409 | `VentaYaCancelada` | Anulando una venta que ya estaba cancelada |
| 409 | `SucursalNoOperativa` | Sucursal inactiva o `permite_ventas = false` |
| 404 | `TurnoNoEncontrado` / `VentaNoEncontrada` | El `id` no existe |
| 422 | (formato) | Falta un campo o el tipo es incorrecto (`cantidad ≤ 0`, `monto ≤ 0`, método de pago inválido…) |

---

## Parte 6 — Checklist para la pantalla POS

- [ ] Al entrar: `GET /caja-turnos/actual`; sin turno → bloquear venta, ofrecer "Abrir caja"
- [ ] **Abrir caja**: input `saldo_inicial`
- [ ] **Vender**: buscador de productos con el preset de 2.0
      (`GET /inventario/productos?activo=true&sucursal_id=…&include=unidades,existencias`;
      por código de barras usa `GET /inventario/productos/resolver-codigo`),
      carrito con cantidad y precio, descuento por línea y total, selección de
      presentación (mostrar `unidades[].imagen_principal`)
- [ ] **Cotizar en vivo**: en cada cambio del carrito, `POST /ventas/cotizar`;
      mostrar `promo_etiqueta` por línea, `promo_descuento`, `total_promociones` y
      el `total` real
- [ ] **Pagos**: uno o varios, con método; mostrar `saldo_pendiente` en vivo
- [ ] Si queda saldo > 0: exigir seleccionar **cliente** antes de cobrar
- [ ] Generar y enviar **`Idempotency-Key`** en el POST de venta; reusarla en reintentos
- [ ] Manejar `StockInsuficiente` / `LimiteCreditoExcedido` sin perder el carrito
- [ ] Al cobrar en efectivo: campo "recibí con" → mandarlo como `monto_recibido`
      en el pago; mostrar el `cambio` que devuelve la venta
- [ ] Ticket / comprobante: pintar el PDF de `GET /ventas/{id}/ticket` (o armar
      uno propio con los campos de la venta: líneas, `total_promociones`,
      `efectivo_recibido`, `cambio`)
- [ ] En cada línea del carrito, si `hay_stock` es `false` en la cotización, marcarla
- [ ] **Monedero** (opcional): campo `telefono`; si viene, `GET /clientes/monedero/{telefono}`
      para mostrar el saldo y ofrecer "pagar con monedero" (`metodo_pago:"monedero"`, ≤ saldo);
      mostrar `monedero_a_generar` (de `cotizar`) y, tras cobrar, `monedero_generado` en el ticket
- [ ] **Historial**: lista de ventas del turno (`?caja_turno_id=`) o por teléfono (`?telefono=`),
      acción "Anular" (con `motivo`)
- [ ] **Devolución**: desde una venta, elegir líneas + cantidades (≤ `cantidad − cantidad_devuelta`),
      método (`efectivo`/`tarjeta`/`credito`/`monedero`), `POST /ventas/{id}/devolucion` con `Idempotency-Key`;
      mostrar el nuevo estado (`devuelta_parcial`/`devuelta_total`) y `total_devuelto`
- [ ] **Cerrar caja**: mostrar `saldo_esperado` (ya descuenta devoluciones en efectivo),
      input `saldo_final_declarado`, mostrar `diferencia`; corte completo →
      `GET /reportes/corte-caja/{turno_id}`
- [ ] Roles: ocultar "Anular ventas viejas" / "Cerrar turno ajeno" si no es admin/gerente;
      "Devolver" requiere `ventas.devolver`
