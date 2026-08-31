from dataclasses import dataclass
from uuid import UUID

PAGINA_TAM_DEFECTO = 50
PAGINA_TAM_MAX = 200

"""
    Paginacion
    Descripcion: Clase que representa la paginacion para listar clientes.
    Atributos:
    - limit: Límite de clientes por página.
    - offset: Offset de clientes por página.
"""
@dataclass
class Paginacion:
    limit: int = PAGINA_TAM_DEFECTO
    offset: int = 0

    def __post_init__(self) -> None:
        self.limit = max(1, min(self.limit, PAGINA_TAM_MAX))
        self.offset = max(0, self.offset)

"""
    FiltroClientes
    Descripcion: Clase que representa el filtro para listar clientes.
    Atributos:
    - sucursal_id: ID de la sucursal.
    - activo: Indica si el cliente está activo.
    - busqueda: Término de búsqueda.
    - con_saldo_pendiente: Indica si el cliente tiene saldo pendiente.
"""
@dataclass
class FiltroClientes:
    sucursal_id: UUID | None = None
    activo: bool | None = None
    busqueda: str | None = None            # coincide contra nombre / email
    con_saldo_pendiente: bool = False      # saldo_credito > 0 (cobranza)


"""
    Pagina
    Descripcion: Clase que representa la página de resultados.
    Atributos:
    - items: Lista de elementos.
    - total: Total de elementos.
"""
@dataclass
class Pagina:
    items: list
    total: int
