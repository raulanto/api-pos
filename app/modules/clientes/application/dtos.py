from dataclasses import dataclass
from uuid import UUID

# La paginación (page/page_size) y el contenedor de resultados `Page` viven en
# la capa transversal: app.shared.responses. Acá sólo el filtro del módulo.
from app.shared.responses import Page  # re-export por compatibilidad de imports

__all__ = ["FiltroClientes", "Page"]


@dataclass
class FiltroClientes:
    """Filtro de listado de clientes. Campos tipados = whitelist implícita."""
    sucursal_id: UUID | None = None
    activo: bool | None = None
    busqueda: str | None = None            # coincide contra nombre / email
    con_saldo_pendiente: bool = False      # saldo_credito > 0 (cobranza)
