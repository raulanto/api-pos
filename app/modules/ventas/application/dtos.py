from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.modules.ventas.domain.value_objects import EstadoVenta

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
class FiltroVentas:
    sucursal_id: UUID | None = None
    caja_turno_id: UUID | None = None
    cliente_id: UUID | None = None
    estado: EstadoVenta | None = None
    desde: datetime | None = None
    hasta: datetime | None = None


@dataclass
class Pagina:
    items: list
    total: int
