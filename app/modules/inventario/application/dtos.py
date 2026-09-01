from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.modules.inventario.domain.value_objects import TipoMovimiento
from app.shared.responses import Page  # re-export por compatibilidad

__all__ = [
    "FiltroProductos", "FiltroMovimientos", "FiltroCategorias", "FiltroExistencias", "Page",
]


@dataclass
class FiltroProductos:
    categoria_id: UUID | None = None
    activo: bool | None = None
    busqueda: str | None = None  # coincide contra nombre / sku / codigo_barras


@dataclass
class FiltroCategorias:
    activo: bool | None = None
    categoria_padre_id: UUID | None = None
    busqueda: str | None = None  # coincide contra nombre


@dataclass
class FiltroExistencias:
    producto_id: UUID | None = None
    sucursal_id: UUID | None = None
    solo_bajo_stock: bool = False


@dataclass
class FiltroMovimientos:
    producto_id: UUID | None = None
    sucursal_id: UUID | None = None
    tipo: TipoMovimiento | None = None
    desde: datetime | None = None
    hasta: datetime | None = None
