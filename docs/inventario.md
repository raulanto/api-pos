# Sistema de Inventario — estado actual y roadmap

> Última actualización: 2026-09-06 · Head de migraciones del proyecto: `f7a8b9c0d1e2`
> Cubre el módulo `app/modules/inventario` y su integración con `ventas`.

Este documento describe **lo que el sistema de inventario hace hoy** y **lo que
está contemplado pero todavía no implementado**. Es la referencia funcional del
módulo; el detalle fino vive en el código y en los docstrings de cada caso de uso.

---

## 1. Panorama

El módulo `inventario` administra el **catálogo de productos** y el **stock por
sucursal**. Sigue arquitectura hexagonal por capas:

```
inventario/
├── domain/
│   ├── entities/         # Categoria, UnidadMedida, Producto, ProductoComponente,
│   │                     # ProductoUnidad, ProductoImagen, InstanciaAbierta,
│   │                     # Lote, ExistenciaLote, Existencia, MovimientoInventario
│   ├── value_objects.py  # TipoMovimiento, TipoProducto, TipoMagnitud, EstadoInstancia
│   └── exceptions.py     # excepciones de dominio (se traducen a HTTP en router/common.py)
├── application/
│   ├── ports/            # interfaces de repositorio (1 por agregado)
│   ├── use_cases/        # 1 archivo por familia de operaciones
│   └── dtos.py           # FiltroProductos, FiltroExistencias, FiltroMovimientos, ProductoKpis
└── infrastructure/
    ├── persistence/
    │   ├── orm_models/   # 1 tabla por archivo
    │   ├── repositories/ # implementación SQLAlchemy de cada port
    │   └── mappers.py    # ORM <-> dominio
    └── api/
        ├── router/       # categorias, unidades_medida, productos, componentes,
        │                 # unidades, imagenes, instancias, lotes, existencias, movimientos
        └── schemas/      # request/response Pydantic v2
```

Reglas transversales del proyecto que aplican aquí:

- **Un request = una transacción.** `get_db()` hace `commit`/`rollback`. Los
  repos y casos de uso sólo hacen `flush()`, nunca `commit()`.
- **Envelope de respuesta** `{success, data, meta, links}` vía `EnvelopeRoute`.
  Listados con `page_response(...)`; recursos sueltos con `ok(entity)`.
- **Traducción de errores** en `router/common.py::traducir()`:
  `*_NoEncontrado/a` → 404, conflictos → 409, `ValueError` y reglas de negocio
  inválidas → 400. El handler global arma `{success:false, error:{code,message,fields?}}`.
- **Alcance por sucursal**: roles globales (admin/gerente) operan sobre cualquier
  sucursal; un rol de sucursal queda atado a la suya (`verificar_alcance_sucursal`,
  `sucursal_efectiva`, `sucursales_efectivas`).
- **Includes**: `?include=a,b` expande relaciones embebidas (`make_include_dependency`).
- **Unicidad "entre activos"**: índices únicos parciales `WHERE activo` — al dar de
  baja un recurso, su clave (SKU, código, nombre) queda libre para reutilizarse.
- **Permisos** (seed por migración): `inventario.leer`, `inventario.crear`,
  `inventario.editar`, `inventario.movimiento`, `inventario.eliminar` (borrado
  físico de producto).

---

## 2. Entidades y tablas

### 2.1 `categoria`

Árbol de categorías (auto-referencia `categoria_padre_id`). Baja lógica
(`activo`). No se puede desactivar una categoría con productos activos.

### 2.2 `unidad_medida` — catálogo normalizado

Reemplaza el texto libre que antes vivía en `producto.unidad_medida`. Sembrada
con 14 filas base (`unidad`, `pza`, `caja`, `paquete`, `reja`, `docena`, `kg`,
`g`, `l`, `ml`, `m`, `cm`, `hora`, `dia`).

| Columna         | Tipo         | Nota |
|-----------------|--------------|------|
| `codigo`        | varchar(20)  | único (mayúsc/minúsc indistinto en lectura) |
| `nombre`        | varchar(60)  | visible |
| `tipo_magnitud` | varchar(20)  | `conteo` \| `masa` \| `volumen` \| `longitud` \| `tiempo` |
| `decimales`     | smallint 0-6 | decimales admitidos para una cantidad en esta unidad (0 = piezas) |
| `activo`        | bool         | baja lógica; no se puede desactivar si está en uso |

`producto.unidad_medida_id` y `producto_unidad.unidad_medida_id` son **FK nullable**
a esta tabla. La columna string `unidad_medida` sigue existiendo como rótulo /
fallback mientras el backfill no esté completo.

### 2.3 `producto`

Registro central del catálogo.

| Columna                     | Tipo          | Nota |
|-----------------------------|---------------|------|
| `sku`                       | varchar(50)   | único **entre activos** |
| `codigo_barras`             | varchar(50)   | único **entre activos**, nullable |
| `nombre`, `descripcion`     | varchar / text| |
| `categoria_id`              | FK categoria  | |
| `unidad_medida`             | varchar(20)   | texto libre (rótulo / fallback) |
| `unidad_medida_id`          | FK unidad_medida | nullable |
| `precio_venta`, `costo`     | numeric(12,2) | volátiles: un movimiento de ENTRADA puede empujar nuevos valores |
| `impuesto_tasa`             | numeric(5,2)  | |
| `tipo`                      | varchar(20)   | enum `TipoProducto` (ver §3) |
| `permite_stock_negativo`    | bool          | permite que SALIDA deje saldo < 0 |
| `permite_venta_fraccionada` | bool          | permite cantidades no enteras de la unidad base |
| `incremento_minimo_venta`   | numeric(14,4) | nullable; si se define, toda venta/salida debe ser múltiplo exacto |
| `requiere_lote`             | bool          | activa el control por lote: ENTRADA con lote obligatorio, SALIDA por FEFO |
| `rastrea_instancia_abierta` | bool          | activa el rastreo de envases abiertos (ver §5.9). Requiere `instancia_capacidad_default` |
| `instancia_capacidad_default` | numeric(14,4) | nullable; capacidad con la que se auto-abre un envase al vender a granel |
| `precio_incluye_impuesto`   | bool          | `precio_venta` ya trae el IVA adentro (precio final al público) |
| `precio_mayoreo`            | numeric(12,2) | nullable; precio alternativo a partir de `cantidad_minima_mayoreo` (ver §5.10) |
| `cantidad_minima_mayoreo`   | numeric(14,4) | nullable; va junto con `precio_mayoreo` (ambos o ninguno) |
| `es_sobre_pedido`           | bool          | no se mantiene en stock; se vende sin existencia (como `permite_stock_negativo`) |
| `activo`                    | bool          | baja lógica |

Relaciones embebidas (`?include=`): `categoria`, `existencias`, `componentes`,
`unidades`, `imagenes`. Además `imagen_principal` va **siempre** en la respuesta
(no depende de `?include=`): es la imagen de la galería marcada `es_principal`, o
`null`.

### 2.4 `producto_componente` — recetas / kits (BOM)

PK compuesta `(producto_kit_id, producto_componente_id)`. Un `producto` con
`tipo = kit` se arma con estas líneas. Checks en BD: `cantidad > 0` y
`producto_kit_id <> producto_componente_id`. Un componente no puede ser a su vez
un kit. Un producto que es componente de un kit **activo** no se puede desactivar.

Al vender un kit, `InventarioPortImpl._expandir` lo explota en sus componentes y
descuenta stock de cada uno (`cantidad_componente × cantidad_vendida`). El kit no
tiene existencia propia.

### 2.5 `producto_unidad` — presentaciones de venta

El stock siempre se lleva en **unidad base** del producto. Cada fila acá es una
presentación alternativa ("Reja x24", "Botella 750ml"…) con su propio precio y,
opcionalmente, su propio código de barras.

| Columna            | Tipo          | Nota |
|--------------------|---------------|------|
| `nombre`           | varchar(50)   | único por producto entre activas |
| `unidad_medida`    | varchar(20)   | rótulo propio ("reja", "litro") |
| `unidad_medida_id` | FK unidad_medida | nullable |
| `factor`           | numeric(12,6) | **unidades base por 1 de esta presentación** (Reja x24 ⇒ 24) |
| `precio_venta`     | numeric(12,2) | precio de 1 presentación (independiente, no derivado) |
| `codigo_barras`    | varchar(50)   | nullable, único entre activas |
| `activo`           | bool          | **baja lógica** (las ventas históricas siguen apuntando a la fila) |

El request de alta acepta `factor` **o** `unidades_por_base` (su recíproco:
"6 latas por reja" ⇒ `unidades_por_base: 6` ⇒ `factor: 0.166667`).

`GET /productos/resolver-codigo?codigo_barras=…` es el punto de escaneo del POS:
resuelve un código contra el producto (unidad base) o contra una presentación y
devuelve `producto_id`, `unidad_id`, `factor` y `precio_venta` a usar en la línea.

### 2.6 `producto_imagen` — galería

Galería de imágenes. Dueño **exactamente uno**: `producto_id` XOR
`producto_unidad_id` (CHECK `(producto_id IS NULL) <> (producto_unidad_id IS NULL)`).
No hay subida de archivos: se registra la **URL** (el cliente sube a su CDN/almacén).

| Columna              | Tipo         | Nota |
|----------------------|--------------|------|
| `url`                | varchar(500) | valida como HttpUrl en el schema |
| `alt_texto`          | varchar(255) | nullable |
| `orden`              | smallint     | posición en el carrusel |
| `es_principal`       | bool         | portada; sólo una por dueño (el caso de uso desmarca la anterior) |

Borrado **físico** (no soft-delete). Endpoints anidados bajo `/productos/{id}/imagenes`
y `/productos/{id}/unidades/{unidad_id}/imagenes`.

### 2.7 `lote` — control por lote (sólo si `producto.requiere_lote`)

Un lote es un ingreso identificable de mercadería (código del proveedor /
fabricante) con su propia caducidad y su propio costo. El lote es del producto,
no de la sucursal: un mismo lote puede tener stock en varias sucursales.

| Columna           | Tipo         | Nota |
|-------------------|--------------|------|
| `producto_id`     | FK producto  | |
| `codigo_lote`     | varchar(60)  | único por producto **entre lotes activos** |
| `fecha_caducidad` | date         | nullable (`NULL` = no vence / sin dato; va al final del orden FEFO) |
| `costo`           | numeric(12,2)| costo unitario (unidad base) de la mercadería de este lote |
| `proveedor`       | varchar(150) | nullable, texto libre |
| `activo`          | bool         | baja lógica; no se puede desactivar con saldo > 0 |

### 2.8 `existencia_lote` — desglose del saldo por lote

Para un producto con `requiere_lote`, `existencia.cantidad` (agregado) = suma de
`existencia_lote.cantidad` de ese producto y sucursal. Una fila por
`(sucursal_id, lote_id)`.

| Columna       | Tipo          | Nota |
|---------------|---------------|------|
| `producto_id` | FK producto   | redundante con `lote.producto_id`, para filtrar |
| `sucursal_id` | FK sucursal   | |
| `lote_id`     | FK lote       | |
| `cantidad`    | numeric(14,4) | saldo del lote en esa sucursal |

### 2.9 `existencia` — saldo de stock por sucursal

Una fila por `(producto_id, sucursal_id)` (constraint único
`uq_existencia_producto_sucursal`). Se crea **de forma perezosa** con el primer
movimiento de esa sucursal.

| Columna        | Tipo          | Nota |
|----------------|---------------|------|
| `cantidad`     | numeric(14,4) | saldo actual en unidad base |
| `stock_minimo` | numeric(14,4) | umbral; se fija en la 1ª ENTRADA o vía `PATCH …/umbrales` |
| `stock_maximo` | numeric(14,4) | nullable |

### 2.8 `movimiento_inventario` — libro de movimientos

Todo cambio de stock deja una fila (append-only).

| Columna               | Tipo          | Nota |
|-----------------------|---------------|------|
| `tipo`                | varchar(20)   | enum `TipoMovimiento` |
| `cantidad`            | numeric(14,4) | siempre positiva, en unidad base |
| `costo_unitario`      | numeric(12,2) | nullable |
| `referencia_tipo`     | varchar(20)   | `compra`, `venta`, `anulacion_venta`, `ajuste`, `transferencia`… |
| `referencia_id`       | uuid          | nullable (id de la venta, etc.) |
| `unidad_capturada_id` | FK producto_unidad | nullable — presentación tal como se capturó antes de convertir a base |
| `cantidad_capturada`  | numeric(14,4) | nullable — cantidad en la presentación capturada |
| `lote_id`             | FK lote       | nullable — lote afectado (productos con control por lote). Una salida FEFO que toca 2 lotes genera 2 filas |
| `instancia_abierta_id`| FK instancia_abierta | nullable — envase abierto del que salió/entró la fracción (ver §5.9) |
| `motivo`              | varchar(255)  | nullable |

### 2.10 `instancia_abierta` — envase físico abierto (sólo si `producto.rastrea_instancia_abierta`)

Un envase destapado con su saldo restante en fracciones de la unidad base
(ej: un galón de 5 L abierto con 3.2 L). Complementa a `existencia` (total) y a
`lote` (FEFO). Detalle completo en `docs/instancia-fisica-abierta.md`.

| Columna | Tipo | Nota |
|---|---|---|
| `producto_id`, `sucursal_id` | FK | |
| `producto_unidad_id` | FK producto_unidad | nullable — presentación origen (define capacidad) |
| `lote_id` | FK lote | nullable — traza caducidad/costo del contenido |
| `capacidad_inicial`, `saldo` | numeric(14,4) | CHECK `0 <= saldo <= capacidad_inicial` |
| `estado` | varchar(12) | `abierta` \| `agotada` \| `descartada` |
| `abierta_por`, `abierta_at`, `cerrada_at`, `motivo_cierre` | | |

---

## 3. Tipos y enums

### `TipoProducto` (`producto.tipo`, VARCHAR — sin `ALTER TYPE`)

| Valor          | Significado |
|----------------|-------------|
| `simple`       | producto unitario; se vende de a piezas enteras |
| `fraccionable` | se vende en fracciones de la unidad base y/o en presentaciones; `permite_venta_fraccionada` se fuerza a `true` |
| `kit`          | se arma con otros productos (BOM); **no lleva stock propio** |
| `servicio`     | no mueve inventario (mano de obra, envíos, cargos) — `tipo.mueve_stock == False` |

### `TipoMovimiento` (`movimiento_inventario.tipo`)

`entrada`, `salida`, `ajuste`, `merma`, `transferencia`.

- **ENTRADA**: suma stock. Puede fijar umbrales (1ª vez) y empujar
  `costo`/`precio_venta` al producto (precios volátiles).
- **SALIDA / MERMA**: resta stock. Valida reglas de fraccionamiento
  (`validar_cantidad_vendible`). Falla con 400 si dejaría saldo < 0 y el producto
  no permite stock negativo.
- **AJUSTE**: fija un `cantidad_final` absoluto; el movimiento registra el delta.
- **TRANSFERENCIA**: no se hace por `POST /movimientos` sino por
  `POST /movimientos/transferencia` (SALIDA en origen + ENTRADA en destino).

### `TipoMagnitud` (`unidad_medida.tipo_magnitud`)

`conteo`, `masa`, `volumen`, `longitud`, `tiempo`.

---

## 4. Endpoints (`/api/v1/inventario`)

### Categorías
| Método | Ruta | Permiso |
|--------|------|---------|
| GET / POST | `/categorias` | leer / crear |
| GET / PATCH | `/categorias/{id}` | leer / editar |
| PATCH | `/categorias/{id}/desactivar` | editar |

### Catálogo de unidades de medida
| Método | Ruta | Permiso |
|--------|------|---------|
| GET / POST | `/unidades-medida` | leer / crear |
| GET / PATCH | `/unidades-medida/{id}` | leer / editar |
| PATCH | `/unidades-medida/{id}/desactivar` · `/reactivar` | editar |

### Productos
| Método | Ruta | Nota |
|--------|------|------|
| GET | `/productos` | filtros: `categoria_id` (multi), `activo`, `q`, `sucursal_id` (multi), `tipo`, `permite_stock_negativo`, `con_codigo_barras`, `precio_min/max`, `costo_min/max`, `solo_bajo_stock`. `?include=categoria,existencias,componentes,unidades,imagenes` |
| POST | `/productos` | acepta `tipo`, `unidad_medida_id`, `permite_venta_fraccionada`, `incremento_minimo_venta`, `requiere_lote`, `rastrea_instancia_abierta` + `instancia_capacidad_default`, `precio_incluye_impuesto`, `precio_mayoreo` + `cantidad_minima_mayoreo`, `es_sobre_pedido` |
| GET | `/productos/kpis` | agregados de catálogo + valuación de stock, mismos filtros que el listado |
| GET | `/productos/buscar?codigo_barras=` | resuelve un producto activo por código |
| GET | `/productos/resolver-codigo?codigo_barras=` | POS: producto **o** presentación + `factor` + `precio_venta` |
| GET / PATCH | `/productos/{id}` | PATCH edita también `sku`, `tipo`, `unidad_medida_id`, flags de fracción/lote/instancia, mayoreo (`cambiar_mayoreo`), IVA-incluido, sobre-pedido (con `cambiar_*` para volver a NULL) |
| PATCH | `/productos/{id}/activar` · `/desactivar` | `desactivar` acepta `?confirmar_con_stock=true` |
| DELETE | `/productos/{id}` | **borrado físico** (producto + imágenes/S3 + presentaciones + kit + lotes + existencia). Permiso `inventario.eliminar`. Rechaza (409) si el producto tiene movimientos o ventas — ahí se usa `/desactivar` |

### Recetas de kit (componentes)
| Método | Ruta |
|--------|------|
| GET / POST / PUT | `/productos/{kit_id}/componentes` (PUT = reemplazar receta completa) |
| PATCH / DELETE | `/productos/{kit_id}/componentes/{componente_id}` |

### Presentaciones de venta (unidades)
| Método | Ruta |
|--------|------|
| GET / POST | `/productos/{id}/unidades` |
| PATCH / DELETE | `/productos/{id}/unidades/{unidad_id}` (DELETE = baja lógica) |

### Galería de imágenes
| Método | Ruta | Nota |
|--------|------|------|
| GET / POST | `/productos/{id}/imagenes` | POST JSON = URL externa |
| POST | `/productos/{id}/imagenes/upload` | **multipart** `file` → sube a S3 (LocalStack en dev), guarda `object_key`; devuelve `url`/`thumbnail_url` prefirmadas. Ver `docs/imagenes-s3-localstack.md` |
| PATCH / DELETE | `/productos/{id}/imagenes/{imagen_id}` | DELETE borra también el objeto y su miniatura de S3 |
| GET / POST · `/upload` | `/productos/{id}/unidades/{unidad_id}/imagenes` | ídem para presentaciones |
| PATCH / DELETE | `/productos/{id}/unidades/{unidad_id}/imagenes/{imagen_id}` | |

### Instancias abiertas (`producto.rastrea_instancia_abierta`)

| Método | Ruta | Permiso |
|--------|------|---------|
| GET | `/productos/{id}/instancias` — `?sucursal_id`, `?estado`, paginado | leer |
| POST | `/productos/{id}/instancias/abrir` — `{sucursal_id, producto_unidad_id? XOR capacidad?, lote_id?, motivo?}` | movimiento |
| GET | `/instancias/{iid}` | leer |
| POST | `/instancias/{iid}/consumir` · `/merma` — `{cantidad, motivo?}` | movimiento |
| POST | `/instancias/{iid}/ajustar` — `{saldo_medido, motivo?}` (sólo baja) | movimiento |
| POST | `/instancias/{iid}/descartar` — `{motivo}` | movimiento |

### Existencias
| Método | Ruta |
|--------|------|
| GET | `/existencias` — `producto_id`, `sucursal_id` (multi) |
| GET | `/existencias/bajo-stock` — `sucursal_id` (multi) |
| GET | `/productos/{producto_id}/existencias` — `sucursal_id` (multi) · **desglose** del saldo a cada presentación (ver §5.11) |
| PATCH | `/existencias/{producto_id}/{sucursal_id}/umbrales` — requiere existencia ya creada |

### Movimientos
| Método | Ruta | Nota |
|--------|------|------|
| GET | `/movimientos` — `producto_id`, `sucursal_id`, `tipo`, `desde`, `hasta`. `?include=producto,usuario` |
| POST | `/movimientos` | `sucursal_id` va en el body; opcionalmente `actualizar_costo` + `costo_unitario`, `nuevo_precio_venta`, `unidad_capturada_id` + `cantidad_capturada`, y para productos con lote: `lote_id` / `lote_nuevo` (ver §5.8) |
| POST | `/movimientos/transferencia` | entre sucursales; valida jerarquía (sólo padre directa o hermanas). Con `requiere_lote`: FEFO-out en origen + ENTRADA al mismo lote en destino (ver §5.8) |
| GET | `/movimientos/{id}` | |

### Lotes

| Método | Ruta | Nota |
|--------|------|------|
| GET | `/lotes/por-vencer` — `dias` (default 30), `sucursal_id` (multi) | panel de caducidades: lotes que vencen dentro de `dias` (incluye vencidos) con su saldo por sucursal |
| GET / PATCH | `/lotes/{lote_id}` | leer / editar código, caducidad, costo, proveedor |
| PATCH | `/lotes/{lote_id}/desactivar` | falla si el lote tiene saldo > 0 |
| GET / POST | `/productos/{producto_id}/lotes` | listar / crear lotes de un producto (`producto.requiere_lote` debe estar activo) |

---

## 5. Reglas de negocio clave

### 5.1 Conversión a unidad base

El stock (`existencia`, `movimiento`) siempre está en **unidad base** del
producto. Una línea de venta puede llevar `producto_unidad_id`; el adapter
convierte `cantidad × factor` a unidad base **redondeando a los `decimales` de la
unidad de medida** (`unidad_medida.decimales`; fallback 4 si el producto no tiene
`unidad_medida_id`). El helper es `_cuantizar(valor, decimales)`.

**Presentación sub-unidad (`factor < 1`)**: si la presentación es *más chica* que
la unidad base (ej: base = "reja" con 0 decimales, presentación "botella" con
`factor = 0.125`), vender 1 botella da `0.125` rejas. En ese caso la cantidad en
unidad base se guarda con **precisión de columna (4 decimales)** en vez de los
`decimales` de la unidad base, y las reglas de §5.2 **no** aplican (se compró una
presentación discreta, no una fracción de reja). La SALIDA resultante lleva
`unidad_capturada_id`, que es la señal de "ya convertido desde una presentación".
Si `cantidad × factor` redondea a 0 igual → 400 pidiendo revisar el `factor`.

### 5.2 Venta fraccionada

`Producto.validar_cantidad_vendible(cantidad)` lanza `CantidadNoVendible` (→ 400) si:

- el producto **no** admite venta fraccionada y la cantidad no es entera, o
- define `incremento_minimo_venta` y la cantidad no es múltiplo exacto.

Se valida en `AplicarMovimientoUseCase` (SALIDA / MERMA) y en el adapter de ventas
(sobre la cantidad base del producto padre), **sólo cuando la venta es en unidad
base** (`producto_unidad_id = None`). Vender una presentación entera se salta esta
regla (ver §5.1). Las ENTRADAS (compras) tampoco tienen esta restricción.

### 5.3 Kits

`tipo = kit` ⇒ sin existencia propia. Al vender, se explota la receta y se
descuenta cada componente. Cambiar `tipo` a/desde `kit` está bloqueado si hay
componentes o presentaciones que lo impidan (`KitInvalido`).

### 5.4 Servicios

`tipo = servicio` ⇒ `mueve_stock == False`. El adapter de ventas salta el
movimiento por completo (no pide existencia, no descuenta nada).

### 5.5 Precios volátiles

`POST /movimientos` (sólo ENTRADA) puede empujar precios al producto dentro de la
misma transacción:

- `actualizar_costo: true` + `costo_unitario` ⇒ `producto.costo = costo_unitario`.
- `nuevo_precio_venta` ⇒ `producto.precio_venta = nuevo_precio_venta`.

Ambos quedan registrados en el evento de auditoría del movimiento.

### 5.6 Existencia perezosa y umbrales

La fila de `existencia` se crea con el primer movimiento de esa sucursal. Los
umbrales (`stock_minimo` / `stock_maximo`) se fijan en esa primera ENTRADA o,
después, con `PATCH /existencias/{p}/{s}/umbrales` (que exige existencia previa).

### 5.7 Trazabilidad de unidad capturada

`movimiento_inventario` guarda `unidad_capturada_id` + `cantidad_capturada` (la
presentación tal como se escaneó, antes de convertir a base). `detalle_venta`
guarda `cantidad_en_unidad_base` (metadato para reportes).

La anulación de venta ya **no** recorre línea por línea: `InventarioPort.revertir_venta(venta_id)`
lee los movimientos de SALIDA que la venta generó y por cada uno registra la
ENTRADA inversa al **mismo lote** y sucursal. Es exacto para kits, presentaciones
y salidas FEFO repartidas entre varios lotes.

### 5.8 Control por lote y FEFO

Si `producto.requiere_lote`:

- **ENTRADA** requiere lote: `lote_id` (existente) o `lote_nuevo`
  (`{codigo_lote, fecha_caducidad?, costo?, proveedor?}` — se crea al vuelo; si el
  código ya existe se reutiliza). Sin lote ⇒ 400 `LoteRequerido`.
- **SALIDA / MERMA / venta** descuentan por **FEFO**: primero el lote que vence
  antes (`fecha_caducidad` asc, `NULL` al final, a igualdad el más viejo). Si una
  salida no entra en un solo lote, se reparte y genera **un movimiento por lote**
  (cada uno con el `costo_unitario` de su lote ⇒ COGS real por lote). `lote_id` en
  el body **fuerza** un lote puntual (override del FEFO).
- **AJUSTE** requiere `lote_id`: `cantidad_final` es el saldo objetivo **de ese
  lote** en la sucursal.
- El saldo vive en `existencia_lote` por `(sucursal, lote)`; `existencia.cantidad`
  se mantiene como la **suma** (fuente única para "cuánto hay").
- Activar `requiere_lote` con stock ya cargado ⇒ 400 (`LoteInvalido`): hay que
  llevar el stock a 0 y recargarlo por lote.
- **Transferencia** entre sucursales: FEFO-out en origen + ENTRADA al **mismo
  `lote_id`** en destino (un lote no es de sucursal, sólo su `existencia_lote`).
  Un traspaso que toca varios lotes genera un par de movimientos por lote.
- `GET /lotes/por-vencer` lista los lotes con caducidad próxima (o vencidos) y su
  saldo por sucursal.

### 5.9 Instancia física abierta

Con `producto.rastrea_instancia_abierta` + `instancia_capacidad_default`: cada
envase destapado se rastrea en `instancia_abierta` con su `saldo` en fracciones.
**Abrir** un envase es neutral (no toca `existencia` ni genera movimiento, sólo
auditoría). **Consumir / merma / descartar / ajustar** generan SALIDA o MERMA
(con `instancia_abierta_id`) y bajan el saldo; en 0 → `agotada`. En una **venta a
granel** (`producto_unidad_id = None`), el módulo `ventas` consume FIFO de las
instancias abiertas y auto-abre las que falten. Detalle: `docs/instancia-fisica-abierta.md`.

### 5.10 Mayoreo, precio con IVA incluido y sobre pedido

- **Mayoreo**: si `precio_mayoreo` + `cantidad_minima_mayoreo` están definidos
  (van juntos), una venta **por unidad base** con `cantidad ≥` el mínimo usa
  `precio_mayoreo` — el backend lo fuerza en `crear_venta` y lo congela en
  `detalle_venta` (ignora el precio del front). Presentaciones (`producto_unidad`)
  usan su propio `precio_venta`.
- **`precio_incluye_impuesto`**: bandera de catálogo — `precio_venta` es el precio
  final con IVA. El módulo `ventas` no calcula impuesto server-side (el total es
  `Σ (cantidad·precio − descuento)`), así que es informativa para el front/reportes.
- **`es_sobre_pedido`**: `Producto.permite_venta_sin_stock = permite_stock_negativo
  or es_sobre_pedido`; las SALIDA / transferencias no fallan por `StockInsuficiente`.

### 5.11 Desglose de stock por presentación

`GET /productos/{id}/existencias` traduce el saldo (en unidad base) a cada
presentación activa, sin recalcular nada. Para "9 rejas menos 1 botella" en un
producto con base = `reja` y presentación `botella` (`factor 0.125`):

```json
{
  "producto_id": "…",
  "unidad_base": "reja",
  "cantidad_base_global": "8.8750",
  "presentaciones_global": [
    { "producto_unidad_id": null, "nombre": "reja",    "factor": "1",     "cantidad": "8.8750", "cantidad_entera": 8 },
    { "producto_unidad_id": "…",  "nombre": "botella", "factor": "0.125", "cantidad": "71.0000","cantidad_entera": 71 }
  ],
  "por_sucursal": [
    { "sucursal_id": "…", "cantidad_base": "8.8750", "stock_minimo": "1", "stock_maximo": "10",
      "presentaciones": [ /* mismo shape */ ] }
  ]
}
```

`cantidad = cantidad_base / factor`; `cantidad_entera = floor(cantidad)`
(presentaciones completas). `?sucursal_id=` (multi) acota el desglose.

---

## 6. Flujos

### 6.1 Alta completa de un producto fraccionable

1. `POST /unidades-medida` (si la unidad no existe en el catálogo) → `unidad_medida_id`.
2. `POST /productos` con `tipo: "fraccionable"`, `unidad_medida_id`,
   `incremento_minimo_venta` (opcional).
3. `POST /productos/{id}/unidades` — presentaciones ("Reja x24", "Botella 750ml").
4. `POST /productos/{id}/imagenes` (y `.../unidades/{uid}/imagenes` para cada
   presentación); marcar una `es_principal`.
5. `POST /movimientos` tipo `entrada` con `stock_minimo` para cargar inventario
   inicial en cada sucursal.

### 6.2 Alta de un kit

1. `POST /productos` con `tipo: "kit"`.
2. `PUT /productos/{kit_id}/componentes` con la receta completa (o `POST` línea a línea).
   El kit **no** recibe movimientos ni existencia propia.

### 6.3 Alta de un producto con control por lote

1. `POST /productos` con `requiere_lote: true` (no se puede activar después si ya
   hay stock).
2. Cada `POST /movimientos` `entrada` indica `lote_nuevo` (crea el lote) o
   `lote_id` (usa uno existente).
3. Las ventas/salidas descuentan solas por FEFO; `GET /lotes/por-vencer` vigila
   las caducidades.

### 6.4 Cargar / corregir inventario

- **Compra**: `POST /movimientos` `entrada`, opcionalmente `actualizar_costo`
  (+ `lote_nuevo`/`lote_id` si el producto lleva lote).
- **Merma**: `POST /movimientos` `merma`.
- **Recuento físico**: `POST /movimientos` `ajuste` con `cantidad_final`
  (+ `lote_id` obligatorio si lleva lote).
- **Entre sucursales**: `POST /movimientos/transferencia` (con lote: FEFO-out + ENTRADA al mismo lote).

### 6.5 Venta (desde el módulo `ventas`)

`CrearVentaUseCase` → por cada línea: aplica `precio_mayoreo` si corresponde
(`InventarioPort.precio_mayoreo_aplicable`, sólo unidad base); llama
`InventarioPort.convertir_a_base(...)` y persiste `cantidad_en_unidad_base` →
`descontar_stock` → si es `servicio` no hace nada; si es `kit` explota la receta;
si `rastrea_instancia_abierta` y es granel consume de instancias abiertas
(FIFO + auto-open); si lleva lote descuenta por FEFO; si no, SALIDA en unidad
base. `AnularVentaUseCase` llama `InventarioPort.revertir_venta(venta_id)`, que
revierte cada SALIDA al mismo lote y repone la instancia abierta si la hubo.

---

## 7. Historial de migraciones del módulo

| Revisión | Contenido |
|----------|-----------|
| `b34c0254a954`, `9d96859233ab` | Módulo de inventario inicial |
| `c1d2e3f4a5b6` | Reinvención de inventario |
| `6308ef5d63b3` | SKU y código de barras únicos sólo entre activos |
| `f1a2b3c4d5e6` | `existencia`: una sola fila de saldo por (producto, sucursal) |
| `a7b8c9d0e1f2` | `producto_componente`: checks de integridad + índice |
| `b8c9d0e1f2a3` | `producto_unidad` (presentaciones) + `detalle_venta.producto_unidad_id` |
| `c9d0e1f2a3b4` · `d0e1f2a3b4c5` | `producto_unidad.unidad_medida` + `factor` numeric(12,6); catálogo `unidad_medida` + FKs |
| `e1a2b3c4d5f6` | catálogo `unidad_medida` + FK desde producto y producto_unidad + seed + backfill por texto |
| `e2b3c4d5f6a7` | `producto.permite_venta_fraccionada` + `incremento_minimo_venta` |
| `e3c4d5e6f7a8` | trazabilidad: `movimiento.unidad_capturada_id`/`cantidad_capturada`, `detalle_venta.cantidad_en_unidad_base` |
| `e4d5e6f7a8b9` | cantidades ampliadas a `numeric(14,4)` (existencia, movimiento, detalle_venta) |
| `f2a3b4c5d6e7` | galería `producto_imagen` |
| `a1c2e3f4b5d6` | control por lote + FEFO: `lote`, `existencia_lote`, `producto.requiere_lote`, `movimiento_inventario.lote_id` |
| `b3d4e5f6a7c8` | `producto_imagen`: almacenamiento en S3 (`object_key`, `content_type`; `url` nullable) |
| `c4d5e6f7a8b9` | seed del permiso `inventario.eliminar` (borrado físico de producto) |
| `d5e6f7a8b9c0` | instancia física abierta: tabla `instancia_abierta`, `producto.rastrea_instancia_abierta` + `instancia_capacidad_default`, `movimiento_inventario.instancia_abierta_id` |
| `f7a8b9c0d1e2` | **(head)** `producto`: `precio_incluye_impuesto`, `precio_mayoreo` + `cantidad_minima_mayoreo`, `es_sobre_pedido` |

---

## 8. Lo que contemplamos (pendiente)

| # | Tema | Estado / decisión |
|---|------|-------------------|
| 1a | **Control por lote + FEFO** | **Implementado** (migración `a1c2e3f4b5d6`). Ver §2.7-2.8 y §5.8. |
| 1b | **Instancia física abierta** (envase abierto vendido en fracciones) | **Implementado** (migración `d5e6f7a8b9c0`). Ver §2.10 y §5.9, y `docs/instancia-fisica-abierta.md`. |
| 1c | **Transferencia entre sucursales de productos con lote** | **Implementado** — FEFO-out en origen + ENTRADA al mismo lote en destino. Ver §5.8. |
| 2 | **Backfill completo de `unidad_medida_id`** | Hoy el backfill es best-effort por match de texto. Falta una pasada de datos + eventualmente hacer la FK `NOT NULL` y dropear la columna string `unidad_medida`. |
| 3 | **Subida de archivos de imagen** | **Implementado** — `POST .../imagenes/upload` (multipart) → S3 (LocalStack en dev), URLs prefirmadas, Lambda de miniaturas. Ver `docs/imagenes-s3-localstack.md`. |
| 4 | **Precio de presentación derivado de la unidad base** | Hoy cada `producto_unidad.precio_venta` es 100% manual e independiente. Contemplado: `producto.precio_por_unidad_base` + flag `precio_derivado` por presentación (precio calculado en lectura = `base × factor`). |
| 5 | **Reportes por presentación** | Los KPIs (`/productos/kpis`) trabajan en unidad base. Ver ventas/stock por presentación requiere un endpoint nuevo con `group by producto_unidad_id`. |
| 6 | **`decimales_permitidos` / redondeo configurable a nivel producto** | Hoy los decimales salen de `unidad_medida.decimales` (fallback 4). Contemplado exponerlo/overridearlo por producto si algún caso lo pide. |
| 7 | **Imagen principal con fallback** | Hoy `imagen_principal` es `null` si nadie marcó una. Contemplado (si se pide): usar la primera por `orden` como portada implícita. |
| 8 | **Seed de permisos propio para `unidad_medida` e `imagenes`** | Hoy reusan `inventario.leer/crear/editar` (igual que categorías). Si se quiere granularidad, agregar `inventario.unidad_medida.*` / `inventario.imagen.*` por migración. |
| 9 | **Reserva de stock / stock comprometido** | No existe. Toda venta descuenta de inmediato. Contemplado si se agregan pedidos/apartados. |
