# Reportes pendientes (ventas por categoría, comparativo, valorización a venta)

> Plan de implementación de los 3 huecos detectados contra el catálogo original
> (ver conversación). Todo se agrega al módulo `reportes` ya existente,
> siguiendo el mismo patrón plano que ya usan `reporte_ventas` /
> `top_productos` / `mermas_y_ajustes`: dataclass de salida en el puerto,
> método en `SqlAlchemyReporteQueryImpl`, caso de uso delegado, schema Pydantic,
> endpoint en el router. Nada de capas nuevas, nada de cache/exportadores.
>
> Permiso: reutilizar `reportes.leer` en los 3, no hace falta sembrar nada.
> Tests: ninguno de los métodos de `reporte_query_impl.py` tiene test (son SQL
> de agregación contra Postgres real, no hay integración en el suite) — no
> romper esa convención agregando el primero acá.

Archivos a tocar en los 3 casos:
- `app/modules/reportes/application/ports/reporte_query_port.py`
- `app/modules/reportes/infrastructure/persistence/reporte_query_impl.py`
- `app/modules/reportes/application/use_cases/consultar_reportes.py`
- `app/modules/reportes/infrastructure/api/schemas.py`
- `app/modules/reportes/infrastructure/api/router.py`

---

## 1. Ventas por categoría

Igual que `top_productos` pero agrupando por `categoria_id` en vez de
`producto_id`. Reutiliza `_LINEA_SUBTOTAL` y `_ventas_validas` ya existentes.

**Puerto** — nueva dataclass + método abstracto:
```python
@dataclass
class CategoriaRankingOutput:
    categoria_id: UUID
    nombre: str
    cantidad_vendida: Decimal
    monto_total: Decimal

@abstractmethod
async def ventas_por_categoria(
    self, desde: datetime, hasta: datetime, sucursal_id: UUID | None = None,
    limit: int = 20, offset: int = 0,
) -> PaginaReporte: ...
```

**Impl** — mismo query que `top_productos`, cambiando el join/group-by a
`CategoriaORM` (join `ProductoORM.categoria_id == CategoriaORM.id`):
```python
async def ventas_por_categoria(self, desde, hasta, sucursal_id=None, limit=20, offset=0):
    cond = self._ventas_validas(desde, hasta, sucursal_id)
    total = await self._db.scalar(
        select(func.count(func.distinct(ProductoORM.categoria_id)))
        .select_from(DetalleVentaORM)
        .join(VentaORM, VentaORM.id == DetalleVentaORM.venta_id)
        .join(ProductoORM, ProductoORM.id == DetalleVentaORM.producto_id)
        .where(*cond)
    )
    filas = (await self._db.execute(
        select(
            CategoriaORM.id, CategoriaORM.nombre,
            func.coalesce(func.sum(DetalleVentaORM.cantidad), 0),
            func.coalesce(func.sum(_LINEA_SUBTOTAL), 0),
        )
        .select_from(DetalleVentaORM)
        .join(VentaORM, VentaORM.id == DetalleVentaORM.venta_id)
        .join(ProductoORM, ProductoORM.id == DetalleVentaORM.producto_id)
        .join(CategoriaORM, CategoriaORM.id == ProductoORM.categoria_id)
        .where(*cond)
        .group_by(CategoriaORM.id, CategoriaORM.nombre)
        .order_by(func.coalesce(func.sum(_LINEA_SUBTOTAL), 0).desc())
        .limit(limit).offset(offset)
    )).all()
    items = [CategoriaRankingOutput(categoria_id=cid, nombre=n,
             cantidad_vendida=Decimal(c or 0), monto_total=Decimal(m or 0))
             for cid, n, c, m in filas]
    return PaginaReporte(items=items, total=int(total or 0))
```

**Caso de uso**: `VentasPorCategoriaUseCase`, delegación fina (calco de
`ProductosMasVendidosUseCase`).

**Schema**: `CategoriaRankingResponse` (calco de `ProductoRankingResponse`).

**Router**: `GET /ventas-por-categoria` — calco exacto de
`productos_mas_vendidos` (mismos query params, `page_response` con
`_filtros_rango`).

---

## 2. Comparativo período actual vs. anterior

No duplicar el cálculo de totales: llamar dos veces al ya existente
`self.reporte_ventas(...)` (período actual y período anterior de igual
duración) desde dentro del propio `reporte_query_impl.py` — es el mismo
patrón de reutilización interna que ya hace `calcular_corte_caja` al reusar
subconsultas.

**Período anterior**: misma duración, inmediatamente antes de `desde`.
```python
duracion = hasta - desde
anterior_hasta = desde
anterior_desde = desde - duracion
```

**Puerto**:
```python
@dataclass
class ComparativoPeriodoOutput:
    actual: ReporteVentasOutput
    anterior: ReporteVentasOutput
    variacion_total_pct: Decimal | None      # None si anterior.total_vendido == 0
    variacion_numero_ventas_pct: Decimal | None

@abstractmethod
async def comparativo_ventas(
    self, desde: datetime, hasta: datetime, sucursal_id: UUID | None = None
) -> ComparativoPeriodoOutput: ...
```

**Impl**:
```python
async def comparativo_ventas(self, desde, hasta, sucursal_id=None):
    duracion = hasta - desde
    anterior_desde, anterior_hasta = desde - duracion, desde
    actual = await self.reporte_ventas(desde, hasta, sucursal_id)
    anterior = await self.reporte_ventas(anterior_desde, anterior_hasta, sucursal_id)

    def _variacion(nuevo, viejo):
        if not viejo:
            return None
        return ((nuevo - viejo) / viejo * 100).quantize(Decimal("0.01"))

    return ComparativoPeriodoOutput(
        actual=actual, anterior=anterior,
        variacion_total_pct=_variacion(actual.total_vendido, anterior.total_vendido),
        variacion_numero_ventas_pct=_variacion(
            Decimal(actual.numero_ventas), Decimal(anterior.numero_ventas)
        ),
    )
```

**Caso de uso**: `ComparativoVentasUseCase`, delegación fina.

**Schema**: `ComparativoPeriodoResponse` con `actual`/`anterior` anidando
`ReporteVentasResponse` y los dos `Optional[Decimal]` de variación.

**Router**: `GET /ventas-comparativo?desde=&hasta=&sucursal_id=` — mismo
`_rango`/`_sucursal_reporte` que el resto.

---

## 3. Valorización a precio de venta (extensión, no endpoint nuevo)

`inventario_valorizado` ya existe y valora a **costo**
(`cantidad * producto.costo`). Agregar el valor a **precio de venta** en
paralelo, sin tocar la firma del método ni crear un endpoint nuevo — solo
sumar campos.

**Puerto** — agregar campos a los dataclasses existentes:
```python
@dataclass
class CategoriaValorizadaOutput:
    categoria_id: UUID
    nombre: str
    valor: Decimal              # a costo (ya existe)
    valor_venta: Decimal        # NUEVO: cantidad * producto.precio_venta
    numero_productos: int

@dataclass
class InventarioValorizadoOutput:
    sucursal_id: UUID | None
    categoria_id: UUID | None
    valor_total: Decimal            # a costo (ya existe)
    valor_venta_total: Decimal      # NUEVO
    por_categoria: list[CategoriaValorizadaOutput] = field(default_factory=list)
```

**Impl** — agregar la segunda expresión de valor y sumarla al mismo query
(un solo round-trip, no dos queries):
```python
valor_expr = func.coalesce(func.sum(ExistenciaORM.cantidad * ProductoORM.costo), 0)
valor_venta_expr = func.coalesce(func.sum(ExistenciaORM.cantidad * ProductoORM.precio_venta), 0)
...
select(CategoriaORM.id, CategoriaORM.nombre, valor_expr, valor_venta_expr,
       func.count(func.distinct(ProductoORM.id)))
...
por_categoria = [CategoriaValorizadaOutput(
    categoria_id=cid, nombre=nombre,
    valor=Decimal(valor or 0), valor_venta=Decimal(valor_venta or 0),
    numero_productos=int(n or 0),
) for cid, nombre, valor, valor_venta, n in filas]

return InventarioValorizadoOutput(
    ...,
    valor_total=sum((c.valor for c in por_categoria), _CERO),
    valor_venta_total=sum((c.valor_venta for c in por_categoria), _CERO),
    por_categoria=por_categoria,
)
```

**Schema**: agregar `valor_venta` a `CategoriaValorizadaResponse` y
`valor_venta_total` a `InventarioValorizadoResponse`.

**Router**: sin cambios (mismo endpoint `/inventario-valorizado`).

---

## Orden sugerido

1. Valorización a venta (el más chico, un solo archivo de lógica real, sin
   caso de uso ni endpoint nuevos).
2. Ventas por categoría (calco directo de `top_productos`).
3. Comparativo de período (el único con lógica propia: cálculo de rango
   anterior y de variación %).
