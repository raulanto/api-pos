from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.modules.inventario.domain.value_objects import TipoMovimiento

# Límites de paginación compartidos por los casos de uso de listado.
PAGINA_TAM_DEFECTO = 50
PAGINA_TAM_MAX = 200


@dataclass
class Paginacion:
    limit: int = PAGINA_TAM_DEFECTO
    offset: int = 0

    def __post_init__(self) -> None:
        self.limit = max(1, min(self.limit, PAGINA_TAM_MAX))
        self.offset = max(0, self.offset)


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


@dataclass
class Pagina:
    items: list
    total: int
