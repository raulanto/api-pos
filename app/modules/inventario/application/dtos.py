from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from app.modules.inventario.domain.value_objects import TipoMovimiento, TipoProducto
from app.shared.responses import Page  # re-export por compatibilidad

__all__ = [
    "FiltroProductos", "FiltroMovimientos", "FiltroCategorias", "FiltroExistencias",
    "ProductoKpis", "Page",
]


@dataclass
class FiltroProductos:
    categoria_id: list[UUID] | None = None
    activo: bool | None = None
    busqueda: str | None = None  # coincide contra nombre / sku / codigo_barras
    # Sólo productos con existencia registrada en alguna de estas sucursales.
    # Si se pide `?include=existencias`, además acota el embed a esas sucursales.
    sucursal_id: list[UUID] | None = None
    tipo: TipoProducto | None = None
    permite_stock_negativo: bool | None = None
    con_codigo_barras: bool | None = None  # True=solo con, False=solo sin
    precio_min: Decimal | None = None
    precio_max: Decimal | None = None
    costo_min: Decimal | None = None
    costo_max: Decimal | None = None
    # Sólo productos con alguna existencia <= stock_minimo (en las sucursales dadas).
    solo_bajo_stock: bool = False


@dataclass
class ProductoKpis:
    """Agregados del catálogo/valuación de inventario para un `FiltroProductos`."""
    total: int
    activos: int
    inactivos: int
    por_tipo: dict[str, int]
    con_codigo_barras: int
    sin_codigo_barras: int
    categorias_distintas: int
    precio_venta_min: Decimal | None
    precio_venta_max: Decimal | None
    precio_venta_promedio: Decimal | None
    costo_min: Decimal | None
    costo_max: Decimal | None
    costo_promedio: Decimal | None
    margen_promedio: Decimal | None            # avg(precio_venta - costo)
    unidades_en_stock: Decimal                  # sum(existencia.cantidad) en alcance
    valor_inventario_costo: Decimal             # sum(cantidad * costo)
    valor_inventario_venta: Decimal             # sum(cantidad * precio_venta)
    productos_con_existencia: int
    productos_sin_existencia: int
    bajo_stock: int                             # productos con existencia <= stock_minimo


@dataclass
class FiltroCategorias:
    activo: bool | None = None
    categoria_padre_id: UUID | None = None
    busqueda: str | None = None  # coincide contra nombre


@dataclass
class FiltroExistencias:
    producto_id: UUID | None = None
    sucursal_id: list[UUID] | None = None  # varias sucursales => OR (IN)
    solo_bajo_stock: bool = False


@dataclass
class FiltroMovimientos:
    producto_id: UUID | None = None
    sucursal_id: UUID | None = None
    tipo: TipoMovimiento | None = None
    desde: datetime | None = None
    hasta: datetime | None = None
