# Guía: promociones, cupones y descuento manual

> Cómo configurar y consumir el módulo de **promociones** (`/api/v1/promociones`)
> y el **descuento manual** del POS. Todo el cálculo de descuentos lo hace el
> backend; el POS manda el precio de lista y ve el resultado en `POST /ventas/cotizar`
> y en la venta.

---

## La idea en dos minutos

- Una **promoción** es una regla de descuento aparte del producto. Apunta a
  **productos**, **presentaciones** o **categorías**, tiene una vigencia (fechas,
  horario, días) y condiciones (monto mínimo, método de pago, segmento de
  cliente, cupón).
- Tipos: **`nxm`** (2x1, 3x2…), **`porcentaje`** (% sobre la línea),
  **`precio_fijo`** (precio unitario forzado; sirve de mayoreo por presentación).
- **Apilado (`combinable`)**: por defecto una promo es **exclusiva** (una por
  línea). Si la marcás `combinable`, se apila **sobre el precio ya descontado**
  junto a otras combinables.
- **Cupones**: una promo puede exigir un **código** (`requiere_cupon`). El cupón
  tiene su propia vigencia y límites de uso (total y por persona).
- **Descuento manual** (`descuento_linea` / `descuento_total` en la venta) es
  otra cosa: lo teclea el cajero, requiere el permiso `ventas.descuento_manual`,
  un **motivo**, y respeta un **tope de % por rol**. Queda auditado.
- Lo que se cobró **se congela** en la venta (`detalle_venta.promo_descuento` +
  el desglose en `detalle_venta_promo`). Editar o apagar la promo **no** cambia
  ventas viejas.
- Una promo **nunca** toca el stock: sólo cambia el precio.

---

## Parte 0 — Puesta en marcha

1. `uv run alembic upgrade head` — deja el head en `b3c4d5e6f7a8` (migraciones
   `e1f2a3b4c5d6`, `a2b3c4d5e6f7`, `b3c4d5e6f7a8`).
2. **Zona horaria**: el horario/días de una promo se interpretan en la hora local
   del negocio. Configurá `APP_TIMEZONE` en `.env` (default
   `America/Mexico_City`). Los `momento` en BD siguen siendo UTC.
3. **Permisos** (ya sembrados por migración):
   - `promociones.leer` / `promociones.crear` / `promociones.editar` → `admin`,
     `gerente`. Cubren también los **cupones**.
   - `ventas.descuento_manual` → `admin`, `gerente`. Sin él, una venta con
     descuento manual se rechaza (403).
4. **Tope de descuento manual por rol** (opcional): tabla `descuento_manual_limite`.
   `admin` y `gerente` quedan con `pct_max = NULL` (sin tope). Para topear al
   cajero (si le das el permiso):
   ```sql
   INSERT INTO descuento_manual_limite (rol_id, pct_max)
   SELECT id, 10 FROM rol WHERE codigo = 'cajero'
   ON CONFLICT (rol_id) DO UPDATE SET pct_max = EXCLUDED.pct_max;
   ```
   (No hay endpoint todavía; se edita por SQL.)

---

## Parte 1 — Crear una promoción

```
POST /api/v1/promociones          (permiso promociones.crear)
```

### Campos

| Campo | ¿Obligatorio? | Qué es |
|---|---|---|
| `nombre` | sí | Único. Se guarda en la venta como etiqueta de la promo |
| `tipo` | sí | `nxm` · `porcentaje` · `precio_fijo` |
| `objetivos` | sí (≥ 1) | Lista. Cada objetivo lleva **exactamente uno** de `producto_id` (línea por unidad base), `producto_unidad_id` (esa presentación) o `categoria_id` (cualquier producto de esa categoría) |
| `prioridad` | no (`100`) | Menor gana. En empate, desempata por `nombre` |
| `combinable` | no (`false`) | `false` = exclusiva por línea. `true` = se apila sobre el residual |
| `tope_descuento` | no | Máximo **$** que esta promo puede descontar **por línea** |
| `monto_minimo_compra` | no | La promo sólo aplica si el **total bruto** de la venta (Σ cantidad·precio, antes de descuentos) llega a este monto |
| `metodo_pago_requerido` | no | La promo sólo aplica si **algún pago** de la venta usa este método (`efectivo`, `tarjeta_credito`, `tarjeta_debito`, `transferencia`, `credito`, `monedero`) |
| `cliente_segmento` | no | La promo sólo aplica si la venta tiene `cliente_id` y ese cliente tiene ese `segmento` |
| `requiere_cupon` | no (`false`) | Si `true`, la promo **no** aplica salvo que la venta traiga un `codigo_cupon` válido que la habilite |
| `sucursales` | no (`[]`) | Lista de sucursales. **Vacío = todas** |
| `vigente_desde` / `vigente_hasta` | no | Ventana de fechas (ISO 8601). Sin fechas, activa mientras `activo` |
| `hora_desde` / `hora_hasta` | no (las dos o ninguna) | Ventana horaria **local** (`"18:00:00"`). Si `hora_desde > hora_hasta` cruza medianoche (ej. `22:00`→`02:00`) |
| `dias_semana` | no | **Bitmask** lun..dom = bit 0..6. Lunes = 1, martes = 2, miércoles = 4, … domingo = 64. Lun+Mié+Vie = `1+4+16 = 21`. `null` = todos |
| `nxm_lleva` / `nxm_paga` | sólo `nxm` | 2x1 → `2` / `1`. Regla: `lleva > paga > 0` |
| `descuento_pct` | sólo `porcentaje` | % a restar (0–100] |
| `precio_fijo` | sólo `precio_fijo` | Precio unitario forzado. Sólo aplica si es **menor** que el de la línea |
| `cantidad_minima` | opcional (`porcentaje` / `precio_fijo`) | La promo aplica sólo si la línea llega a esa cantidad. Así se arma un mayoreo por presentación |

> **NxM y presentaciones:** una promo `nxm` **no puede** mezclar `producto_id` y
> `producto_unidad_id` (rechaza con 400). El pool cuenta unidades por línea, así
> que una lata suelta y un six-pack contarían mal juntos. Creá una promo por cada
> forma de venta.

---

## Parte 2 — Cómo se aplica en la venta

El backend, al cobrar (y al **cotizar**), corre este pipeline por línea:

```
precio de lista (POS)
  → mayoreo simple de unidad base (producto.precio_mayoreo)   [ver guía de ventas]
  → PROMOCIONES:
      1. candidatas = promos que pasan TODOS los filtros:
         activo · ventana de fechas · sucursal · día de la semana · hora local
         · monto_minimo_compra ≤ total bruto
         · metodo_pago_requerido presente en los pagos
         · cliente_segmento == segmento del cliente de la venta
         · si requiere_cupon: sólo si un cupón válido la habilitó
      2. se parten en EXCLUSIVAS (combinable=false) y COMBINABLES, cada grupo
         ordenado por (prioridad, nombre)
      3. por línea, residual = cantidad × precio:
         - la primera EXCLUSIVA que matchee y descuente > 0 toma la línea
           (acotada a su tope_descuento y al residual) → la línea queda CERRADA
         - si no hubo exclusiva, las COMBINABLES se aplican en orden, cada una
           sobre el RESIDUAL (%, precio_fijo o nxm), acotada a su tope y al residual
  → subtotal_linea = cantidad·precio − descuento_linea − promo_descuento
total = Σ subtotal_linea − descuento_total          (el impuesto NO se suma)
```

- `detalle_venta.promo_descuento` = **Σ de todas** las promos aplicadas a la
  línea. `detalle_venta_promo` (y `lineas[].promos_aplicadas` en la respuesta)
  trae el **desglose** (una fila por promo con su monto). `promo_id` /
  `promo_etiqueta` quedan con la promo de **mayor** monto.
- **NxM** junta las unidades enteras de todas las líneas del mismo objetivo
  (cross-line) y regala las más baratas. Ignora cantidades con decimales.
- El motor es **defensivo**: una promo mal configurada simplemente no aplica, no
  rompe la venta.

### Previsualizar (`cotizar`)

```
POST /api/v1/ventas/cotizar
{
  "lineas": [ { "producto_id": "…", "cantidad": 6, "precio_unitario": 30 } ],
  "metodos_pago": ["transferencia"],      // hint: para ver promos por método de pago
  "cliente_segmento": "vip",              // hint: para ver promos por segmento
  "codigo_cupon": "VERANO25",             // hint: para ver la promo del cupón
  "telefono": "5550001234"
}
```

La respuesta trae por línea `promo_descuento`, `promo_etiqueta`,
`promos_aplicadas[]`, y `total_promociones` / `total` en la venta.

---

## Parte 3 — Cupones

Un **cupón** es un código que habilita una promoción `requiere_cupon = true`.
Cuelga de la promoción.

```
POST  /api/v1/promociones/{promocion_id}/cupones     (permiso promociones.crear)
GET   /api/v1/promociones/{promocion_id}/cupones     (permiso promociones.leer)
PATCH /api/v1/promociones/cupones/{codigo}/desactivar (permiso promociones.editar)
POST  /api/v1/ventas/cupon/validar                   (permiso ventas.crear) — preview
```

### Crear un cupón

```json
POST /api/v1/promociones/<promo_id>/cupones
{
  "codigo": "VERANO25",
  "vigente_desde": "2026-12-01T00:00:00Z",
  "vigente_hasta": "2026-12-31T23:59:59Z",
  "max_usos_total": 500,
  "max_usos_por_persona": 1
}
```

- `codigo` se guarda en **mayúsculas** y es único en todo el sistema.
- `max_usos_total` / `max_usos_por_persona` son opcionales (`null` = sin límite).
  "Por persona" se cuenta por `cliente_id` si la venta lo trae; si no, por
  `telefono`.

### Usar el cupón en la venta

```json
POST /api/v1/ventas/
{
  "caja_turno_id": "…",
  "codigo_cupon": "VERANO25",
  "cliente_id": "…",              // o "telefono": "…" ; sirve para el límite por persona
  "lineas": [ … ],
  "pagos": [ … ]
}
```

- El backend valida el cupón (vigencia + límites) y, si la promo que habilita
  descuenta algo, **registra el uso** en la misma transacción, con `SELECT … FOR
  UPDATE` sobre el cupón: dos ventas simultáneas no pasan el `max_usos_total`.
- Si el cupón está vencido → 400 `CuponVencido`. Si no existe → 404
  `CuponNoEncontrado`. Si agotó sus usos → 409 `CuponAgotado`. En todos los casos
  **la venta no se crea**.
- **Anular** una venta libera sus usos de cupón (vuelven al conteo disponible).
  Una **devolución parcial** no los toca.

`POST /api/v1/ventas/cupon/validar { "codigo": "VERANO25", "cliente_id": "…" }`
devuelve `{ "promocion_id": "…", "valido": true }` sin consumir nada — para que
el POS muestre "cupón aplicado" antes de cobrar.

---

## Parte 4 — Descuento manual en el POS

Cuando el cajero teclea un descuento libre (`descuento_linea` en una línea o
`descuento_total` sobre la venta):

- Requiere el permiso **`ventas.descuento_manual`** → si no, 403
  `DescuentoManualNoAutorizado`.
- Requiere **`motivo_descuento`** en el cuerpo de la venta → si no, 400
  `MotivoDescuentoRequerido`. El motivo se congela en `venta.motivo_descuento`.
- Respeta el **tope de % por rol** (`descuento_manual_limite.pct_max`, `NULL` =
  sin tope). Si el `descuento_linea / (cantidad·precio)` o el
  `descuento_total / total_bruto` supera el tope → 400
  `DescuentoManualExcedeTope`.
- Queda **auditado**: evento `DescuentoManualAplicado` → aparece en
  `GET /api/v1/auditoria` con usuario, montos y motivo.

```json
POST /api/v1/ventas/
{
  "caja_turno_id": "…",
  "motivo_descuento": "producto con caja golpeada",
  "descuento_total": 20,
  "lineas": [ { "producto_id": "…", "cantidad": 1, "precio_unitario": 200,
               "descuento_linea": 15 } ],
  "pagos": [ { "monto": 165, "metodo_pago": "efectivo" } ]
}
```

> El descuento manual y las promociones **conviven**: `promo_descuento` se calcula
> aparte, sobre el `precio_unitario` (ya con mayoreo). El `descuento_linea` manual
> resta además.

---

## Parte 5 — Editar / desactivar

`PATCH /api/v1/promociones/{id}` — sólo los campos que cambian. Para **limpiar**
un grupo de opcionales hay que mandar su **flag**:

| Flag | Qué limpia/cambia si va en `true` |
|---|---|
| `cambiar_topes` | `tope_descuento` + `monto_minimo_compra` (a lo que mandes, o a `null` si no van) |
| `cambiar_condiciones` | `metodo_pago_requerido` + `cliente_segmento` (+ `requiere_cupon` si lo mandás) |
| `cambiar_sucursales` | reemplaza `sucursales` (lista vacía → todas) |
| `cambiar_vigencia` | `vigente_desde` + `vigente_hasta` |
| `cambiar_horario` | `hora_desde` + `hora_hasta` + `dias_semana` |
| `cambiar_cantidad_minima` | `cantidad_minima` |
| `objetivos` | si lo mandás, **reemplaza** la lista completa |

`PATCH …/desactivar` y `…/reactivar` prenden/apagan sin borrar. Las promos no se
borran (append-only), y las ventas viejas nunca se recalculan.

---

## Parte 6 — Recetas

**2x1 en un refresco (unidad base), martes y jueves, 6–9pm:**

```json
{
  "nombre": "2x1 Cola Martes/Jueves happy hour",
  "tipo": "nxm", "nxm_lleva": 2, "nxm_paga": 1, "prioridad": 10,
  "dias_semana": 10,                        // martes(2) + jueves(8)
  "hora_desde": "18:00:00", "hora_hasta": "21:00:00",
  "objetivos": [ { "producto_id": "<cola>" } ]
}
```

**Mayoreo de la reja (presentación) por volumen y con vigencia:**

```json
{
  "nombre": "Reja a $340 llevando 5+",
  "tipo": "precio_fijo", "precio_fijo": 340, "cantidad_minima": 5,
  "vigente_desde": "2026-09-01T00:00:00Z", "vigente_hasta": "2026-09-30T23:59:59Z",
  "objetivos": [ { "producto_unidad_id": "<Reja x24>" } ]
}
```

**10% en toda una categoría, sólo en 2 sucursales, con compra mínima:**

```json
{
  "nombre": "Septiembre -10% Botanas",
  "tipo": "porcentaje", "descuento_pct": 10,
  "monto_minimo_compra": 150,
  "sucursales": ["<suc A>", "<suc B>"],
  "objetivos": [ { "categoria_id": "<Botanas>" } ]
}
```

**Combinable: 5% socio que se apila sobre el 2x1, con tope de $50:**

```json
{
  "nombre": "5% Socio",
  "tipo": "porcentaje", "descuento_pct": 5,
  "combinable": true, "tope_descuento": 50, "prioridad": 90,
  "cliente_segmento": "socio",
  "objetivos": [ { "categoria_id": "<Bebidas>" } ]
}
```
Si la línea también matchea el "2x1 Cola" (exclusiva), **gana el 2x1** y el 5% no
se apila (sólo se apilan combinables entre sí). Si la línea sólo matchea el 5%,
se aplica el 5% (topado a $50).

**15% sólo pagando por transferencia:**

```json
{
  "nombre": "-15% Transferencia",
  "tipo": "porcentaje", "descuento_pct": 15,
  "metodo_pago_requerido": "transferencia",
  "objetivos": [ { "producto_id": "<X>" } ]
}
```

**Promo por cupón (código `BIENVENIDA`, un uso por cliente):**

```json
1) POST /api/v1/promociones
   { "nombre": "Bienvenida -20%", "tipo": "porcentaje", "descuento_pct": 20,
     "requiere_cupon": true, "objetivos": [ { "categoria_id": "<Todo>" } ] }
2) POST /api/v1/promociones/<id>/cupones
   { "codigo": "BIENVENIDA", "max_usos_por_persona": 1 }
3) POST /api/v1/ventas/  { …, "codigo_cupon": "BIENVENIDA", "cliente_id": "…" }
```

---

## Parte 7 — Errores

| Código | Error | Qué pasó |
|---|---|---|
| 400 | `PromocionInvalida` / (formato) | Params incoherentes con el `tipo`, `dias_semana` fuera de 1–127, NxM mezcla base y presentación, objetivo sin exactamente uno de los tres ids, etc. |
| 409 | (conflicto) | `nombre` de promo repetido, o `codigo` de cupón repetido, o producto/categoría inexistente |
| 404 | `PromocionNoEncontrada` / `CuponNoEncontrado` | El `id` / `codigo` no existe |
| 400 | `CuponVencido` | El cupón está fuera de su ventana o desactivado (venta no creada) |
| 409 | `CuponAgotado` | El cupón llegó a `max_usos_total` o `max_usos_por_persona` (venta no creada) |
| 403 | `DescuentoManualNoAutorizado` | La venta tiene descuento manual y el usuario no tiene `ventas.descuento_manual` |
| 400 | `MotivoDescuentoRequerido` | Hay descuento manual sin `motivo_descuento` |
| 400 | `DescuentoManualExcedeTope` | El % de descuento manual supera el tope del rol |

Las promociones **nunca** generan un error de venta por sí solas: si una promo no
puede aplicar, simplemente no aplica.

---

## Parte 8 — Checklist para el equipo del POS

- [ ] En cada cambio del carrito, `POST /ventas/cotizar` con los **hints**
      (`metodos_pago`, `cliente_segmento`, `codigo_cupon`, `telefono`) para
      mostrar el total real, `promos_aplicadas` por línea y `total_promociones`.
- [ ] Campo **cupón**: al ingresarlo, `POST /ventas/cupon/validar` para
      confirmar y mostrar la promo; mandarlo como `codigo_cupon` en la venta.
- [ ] Descuento manual: sólo habilitar el campo si el usuario tiene
      `ventas.descuento_manual`; exigir **motivo**; mostrar el error de tope sin
      vaciar el carrito.
- [ ] La etiqueta de promo en el ticket sale de `promo_etiqueta`; si
      `promos_aplicadas` tiene más de una fila, listarlas.
- [ ] Nada de lógica de descuento en el front: sólo mandar precios de lista y
      leer lo que devuelve el backend.

---

## Apéndice — Arquitectura (para devs)

- Motor puro y testeable: `app/modules/promociones/domain/services.py::evaluar(promos, lineas, ctx)`
  con `ContextoEvaluacion` (`domain/value_objects.py`). `Promocion._validar()` sólo
  corre en `crear()/actualizar()`, no al hidratar de BD.
- `EvaluarPromocionesUseCase` = `listar_vigentes` + `evaluar`. `ValidarCuponUseCase`
  (preview) / `ConsumirCuponUseCase` (`FOR UPDATE`, al persistir la venta).
- Enganche en ventas: `PromocionesPort` + `PromocionesPortImpl` (misma
  `AsyncSession` del request). `CrearVentaUseCase` / `AnularVentaUseCase` reciben
  el puerto como opcional. `DescuentoConfigPort` para el tope por rol.
- Tablas: `promocion`, `promocion_objetivo`, `promocion_sucursal`, `cupon`,
  `cupon_uso`, `detalle_venta_promo`, `descuento_manual_limite`.
- Ceilings deliberados (`ponytail:` en el código): NxM combinable regala al precio
  de lista; sin jerarquía de categorías; `APP_TIMEZONE` global (no por sucursal);
  `cliente.segmento` es texto libre; `descuento_manual_limite` se edita por SQL;
  el `monto_descontado` que se guarda en `cupon_uso` es `venta.total_promociones`
  (no el prorrateo por promo). Combos multi-producto = fuera de alcance.
