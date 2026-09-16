# Guía: venta por peso o volumen (para la app)

> Cómo dar de alta algo que se vende "al kilo" (verdura, azúcar a granel) y
> cómo la báscula/el input de cantidad se convierte en el total a cobrar.
> No es un módulo nuevo: es el mismo `tipo: "fraccionable"` de
> `docs/guia-alta-de-productos.md` y las mismas ventas de
> `docs/guia-ventas-y-caja.md`, aplicado a este caso puntual.

---

## La idea en dos minutos

Un producto que se vende por peso es **un solo SKU con stock en su unidad
base** (kg, l) — no hay "unidad" separada por cada kilo. El costal de azúcar
que llega del proveedor entra al mismo producto con `cantidad: 25` (kg); cada
venta descuenta directo de ese saldo.

El cajero no manda un precio: manda **lo que marcó la báscula**. El backend
calcula `cantidad × precio_unitario`, sin conversión de por medio.

```
subtotal = cantidad (kg leídos) × precio_unitario ($/kg)
```

---

## Paso 1 — Unidad de medida

`GET /api/v1/inventario/unidades-medida` ya trae, entre otras, estas cuatro
(permiso `inventario.leer`):

| `codigo` | `nombre` | `tipo_magnitud` | `decimales` |
|---|---|---|---|
| `kg` | Kilogramo | masa | 3 |
| `g` | Gramo | masa | 0 |
| `l` | Litro | volumen | 3 |
| `ml` | Mililitro | volumen | 0 |

`decimales` es cuántos dígitos después del punto tiene sentido para esa
unidad — úsalo para limitar el input del peso en la pantalla.

## Paso 2 — Registrar el producto

`POST /api/v1/inventario/productos` (permiso `inventario.crear`). Detalle
completo de todos los campos en `docs/guia-alta-de-productos.md`; acá sólo los
que importan para este caso:

- `tipo: "fraccionable"` → activa `permite_venta_fraccionada` solo.
- `unidad_medida_id` → el `id` de `kg` (o `l`) del paso 1.
- `precio_venta` → precio de **1 kg completo**, no del costal.
- `incremento_minimo_venta` (opcional) → si la báscula sólo puede pesar de a
  saltos (ej. 50 g), fuerza que la cantidad sea múltiplo exacto. Si el
  producto se vende a cualquier peso (el azúcar suelta, pesada al gramo),
  se omite.

**Verdura suelta — $15.00/kg, sólo de a 50 g:**

```json
{
  "sku": "VERD-001",
  "nombre": "Verdura suelta",
  "categoria_id": "…",
  "unidad_medida": "kg",
  "unidad_medida_id": "<id de kg>",
  "tipo": "fraccionable",
  "precio_venta": 15.00,
  "costo": 9.00,
  "impuesto_tasa": 0,
  "incremento_minimo_venta": 0.050
}
```

**Azúcar a granel — $14.00/kg, cualquier peso:**

```json
{
  "sku": "AZUC-BULTO",
  "nombre": "Azúcar a granel",
  "categoria_id": "…",
  "unidad_medida": "kg",
  "unidad_medida_id": "<id de kg>",
  "tipo": "fraccionable",
  "precio_venta": 14.00,
  "costo": 10.50,
  "impuesto_tasa": 0
}
```

Después, `POST /api/v1/inventario/movimientos` tipo `entrada` con
`cantidad: 25` carga el costal completo en kg (ver "Paso 6" de
`docs/guia-alta-de-productos.md`).

## Paso 3 — Cotizar lo que marca la báscula

El peso leído va tal cual en `cantidad`, sin `producto_unidad_id` (se vende en
la unidad base):

```
POST /api/v1/ventas/cotizar
{
  "lineas": [
    { "producto_id": "<id Verdura suelta>", "cantidad": 0.350, "precio_unitario": 15.00 }
  ]
}
```

```json
{
  "lineas": [
    { "cantidad": 0.350, "precio_unitario": 15.00, "subtotal": 5.25, "hay_stock": true }
  ],
  "total": 5.25
}
```

`cotizar()` corre la **misma validación de fraccionamiento** que el cobro
real (ver tabla abajo): si la báscula marcó `0.347` en un producto con
incremento `0.050`, el error sale acá, antes de cobrar.

## Paso 4 — Confirmar el cobro

Igual que cualquier venta (`docs/guia-ventas-y-caja.md` §2.1), mismo par
`cantidad`/`precio_unitario`:

```
POST /api/v1/ventas
{
  "caja_turno_id": "<turno abierto>",
  "lineas": [
    { "producto_id": "<id Verdura suelta>", "cantidad": 0.350, "precio_unitario": 15.00 }
  ],
  "pagos": [
    { "monto": 5.25, "metodo_pago": "efectivo", "monto_recibido": 10.00 }
  ]
}
```

Si el peso es válido: se descuentan `0.350` kg del stock. Si no, la venta
completa se revierte (venta + pago + stock son la misma transacción).

## Reglas de validación (`Producto.validar_cantidad_vendible`)

| Regla | Ejemplo |
|---|---|
| `cantidad` debe ser `> 0` | `0` o negativo → rechazado |
| Si el producto **no** es fraccionable, la cantidad debe ser entera | `2.5` en un producto `simple` → rechazado |
| Si hay `incremento_minimo_venta`, la cantidad debe ser múltiplo exacto | Verdura (incremento `0.050`): `0.350` pasa, `0.347` no |
| Sin `incremento_minimo_venta`, cualquier peso positivo sirve | Azúcar: `0.238` kg pasa |

Se valida tanto al cobrar como al cotizar — mismo mensaje de error en los dos
casos.

## No es la única forma de vender lo mismo

Todo lo de arriba es **una** configuración (venta por peso real). El sistema
no te obliga a esa: para el mismo tomate (o una caja de tornillos) hay otras
dos formas igual de válidas, y elegís una por producto según cómo lo vendas en
el mostrador.

### A) Por kilo, sobre el peso real — lo de arriba

Se pesa cada venta, se cobra `cantidad_real × precio_venta`. La reja/caja es
sólo cómo entra del proveedor; el cliente nunca la ve como unidad de venta.

### B) Por pieza, a precio fijo

El cajero vende "N piezas" sin pesar nada (3 tomates, 12 tornillos), a un
precio fijo que vos definís. Es un producto **normal**, no fraccionable — no
hay conversión de `$/kg` a `$/pieza`: cada tomate no pesa igual, así que si
querés precio por pieza lo fijás vos, no lo calcula el sistema.

```json
{
  "sku": "TOM-PZA", "nombre": "Tomate (pieza)",
  "unidad_medida": "pieza", "precio_venta": 1.80,
  "costo": 1.00, "impuesto_tasa": 0
}
```

```json
{
  "sku": "TORN-3-8", "nombre": "Tornillo 3/8\"",
  "unidad_medida": "pieza", "precio_venta": 2.50,
  "costo": 1.30, "impuesto_tasa": 16
}
```

Venta: `cantidad: 3` (piezas), sin decimales — `validar_cantidad_vendible`
rechaza `2.5` piezas porque el producto no es fraccionable (tabla de arriba).

### C) La reja/caja como lo que se vende, más una presentación suelta

Acá el producto **es** la reja/caja completa (tiene su propio stock, se vende
entera — ej. mayoreo a otro comercio), y la venta suelta es una
**presentación** (`producto_unidad`) con un `factor` aproximado. Mismo patrón
que "lata y reja" de `docs/guia-alta-de-productos.md` (caso B), aplicado a
algo que no tiene un conteo exacto por caja:

```json
// 1. POST /productos — unidad base = la reja completa
{
  "sku": "REJA-TOM", "nombre": "Reja de tomate",
  "unidad_medida": "reja", "precio_venta": 130.00,
  "costo": 100.00, "impuesto_tasa": 0
}
```

```json
// 2. POST /productos/{id}/unidades — venta suelta, factor aproximado
{
  "nombre": "Tomate suelto",
  "unidad_medida": "pieza",
  "factor": 0.025          // ≈ 40 piezas por reja, un promedio — no exacto
}
```

⚠️ El `factor` es fijo y exacto en el sistema (`cantidad_base = cantidad ×
factor`), pero el peso/conteo real de una reja agrícola **no** lo es — cada
reja trae más o menos piezas. Si vendés 15 "tomates sueltos" contra un
`factor` de 40/reja, descuenta `15 × 0.025 = 0.375` rejas del stock aunque la
reja real haya traído 38 o 42; el desfase se corrige con un `AJUSTE`
periódico (`POST /movimientos` tipo `ajuste`) cuando hacés inventario físico.
Para algo que se pesa exacto en cada venta, la opción A) no tiene este
problema — por eso es la recomendada para fruta/verdura.

**Las tres conviven en el catálogo**: no hay nada que te fuerce a elegir una
sola para todo el negocio — el tomate puede ser "por kilo" (A) y los
tornillos "por pieza" (B), o incluso el mismo tomate tener una versión
mayorista "por reja" (C) además de su venta suelta por kilo (A) como **dos
productos distintos** (no se pueden mezclar A y C en el mismo SKU: la unidad
base de un producto es una sola).

## Checklist

- [ ] `unidad_medida_id` = kg/l elegido (paso 1)
- [ ] Producto con `tipo: "fraccionable"` y `precio_venta` por unidad base
- [ ] `incremento_minimo_venta` sólo si la báscula/el negocio lo exige
- [ ] Stock inicial cargado en la unidad base (kg), no en "costales"
- [ ] El POS manda `cantidad` = peso leído, sin `producto_unidad_id`
- [ ] `POST /ventas/cotizar` antes de cobrar para mostrar el total y avisar errores de peso
