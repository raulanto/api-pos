from dataclasses import dataclass
from uuid import UUID

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
class FiltroClientes:
    sucursal_id: UUID | None = None
    activo: bool | None = None
    busqueda: str | None = None            # coincide contra nombre / email
    con_saldo_pendiente: bool = False      # saldo_credito > 0 (cobranza)


@dataclass
class Pagina:
    items: list
    total: int
