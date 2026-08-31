from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.modules.inventario.domain.value_objects import TipoMovimiento
from app.shared.responses import Page  # re-export por compatibilidad

__all__ = ["FiltroProductos", "FiltroMovimientos", "Page"]


@dataclass
class FiltroProductos:
    categoria_id: UUID | None = None
    activo: bool | None = None
    busqueda: str | None = None  # coincide contra nombre / sku / codigo_barras


@dataclass
class FiltroMovimientos:
    producto_id: UUID | None = None
    sucursal_id: UUID | None = None
    tipo: TipoMovimiento | None = None
    desde: datetime | None = None
    hasta: datetime | None = None
