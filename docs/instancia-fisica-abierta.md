# Instancia física abierta (envase destapado vendido en fracciones)

Rastrea **cada envase concreto que se destapó** para vender su contenido en
fracciones de la unidad base (p. ej. un galón de 5 L abierto con 3.2 L
restantes). Complementa a `existencia` (total en unidad base) y a `lote` (FEFO).

## Modelo

- `producto.rastrea_instancia_abierta` (bool) — activa el rastreo por producto.
- `producto.instancia_capacidad_default` (NUMERIC 14,4) — obligatorio si el flag
  está en `true`; capacidad con la que se **auto-abre** un envase al vender a granel.
- `instancia_abierta` — un envase: `capacidad_inicial`, `saldo`, `estado`
  (`abierta` \| `agotada` \| `descartada`), `lote_id` (traza caducidad/costo),
  `producto_unidad_id` (presentación origen), `abierta_por`/`abierta_at`,
  `cerrada_at`/`motivo_cierre`. Invariante: `0 <= saldo <= capacidad_inicial`.
- `movimiento_inventario.instancia_abierta_id` — de qué envase salió/entró la fracción.

### Contabilidad

| Operación | `existencia` | `movimiento_inventario` | `instancia.saldo` |
|---|---|---|---|
| **Abrir** | sin cambio | — (solo evento auditoría) | nace en `capacidad` |
| **Consumir / venta a granel** | baja | SALIDA (con `instancia_abierta_id`) | baja; 0 → `agotada` |
| **Merma** | baja | MERMA | baja |
| **Descartar** | baja por el remanente | MERMA | 0, `descartada` |
| **Ajustar** (medición ≤ saldo) | baja por la diferencia | MERMA | = medición |
| **Anular venta** | repone | ENTRADA inversa | repone; reabre si estaba `agotada` |

"Sellado disponible" es derivado: `existencia.cantidad - Σ saldo de instancias abiertas`.

## Endpoints (`/api/v1/inventario`)

| Método | Ruta | Permiso |
|---|---|---|
| `GET` | `/productos/{id}/instancias` (`?sucursal_id`, `?estado`, paginado) | `inventario.leer` |
| `POST` | `/productos/{id}/instancias/abrir` | `inventario.movimiento` |
| `GET` | `/instancias/{iid}` | `inventario.leer` |
| `POST` | `/instancias/{iid}/consumir` `{cantidad, motivo?}` | `inventario.movimiento` |
| `POST` | `/instancias/{iid}/merma` `{cantidad, motivo?}` | `inventario.movimiento` |
| `POST` | `/instancias/{iid}/ajustar` `{saldo_medido, motivo?}` | `inventario.movimiento` |
| `POST` | `/instancias/{iid}/descartar` `{motivo}` | `inventario.movimiento` |

`abrir`: body `{sucursal_id, producto_unidad_id? XOR capacidad?, lote_id?, motivo?}`.
Sin presentación ni capacidad usa `instancia_capacidad_default`.

## Integración con ventas

Una línea de venta **a granel** (sin `producto_unidad_id`) de un producto que
rastrea instancias consume FIFO de las instancias `abierta` de esa sucursal
(la más vieja primero); si falta saldo, **auto-abre** envases de
`instancia_capacidad_default` (lote FEFO). Cada tramo es un SALIDA con su
`instancia_abierta_id`. Vender una **presentación sellada** sigue la ruta normal
(SALIDA/FEFO sin instancias). Anular la venta repone cada instancia.

Código: `app/modules/ventas/infrastructure/adapters/inventario_port_impl.py`
(`_descontar_una` / `_consumir_de_instancias`).

## Verificación

1. `uv run alembic upgrade head`.
2. Producto FRACCIONABLE con `rastrea_instancia_abierta=true`,
   `instancia_capacidad_default=5`, presentación "Galón 5L" `factor=5`.
3. `POST /movimientos` ENTRADA 20 → `existencia = 20`.
4. `POST /productos/{id}/instancias/abrir {"producto_unidad_id": "<galon>"}` →
   `saldo=5`, `existencia` sigue 20.
5. `POST /instancias/{iid}/consumir {"cantidad": "3.2"}` → `saldo=1.8`,
   `existencia=16.8`; hay SALIDA con `instancia_abierta_id`.
6. `POST /instancias/{iid}/merma {"cantidad": "1.8"}` → `agotada`, `existencia=15`.
7. Venta a granel de 2 L sin instancias abiertas → auto-abre (cap 5),
   `saldo=3`, `existencia=13`.
8. Anular la venta → instancia `saldo=5`, `existencia=15`.
9. `uv run pytest`.

## Límites

- `ajustar` solo baja: una medición mayor al saldo registrado → 400 (abrir otra
  instancia, no inflar una).
- El auto-open al vender usa una capacidad fija; no calza varias presentaciones.
- Un envase `descartada` no se resucita al anular la venta (solo repone el agregado).
