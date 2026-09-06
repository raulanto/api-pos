from dataclasses import dataclass
from uuid import UUID

from app.modules.sucursales.domain.entities import TipoSucursal


@dataclass
class FiltroSucursales:
    activo: bool | None = None
    busqueda: str | None = None  # coincide contra nombre / dirección / teléfono / codigo
    tipo: TipoSucursal | None = None
    sucursal_padre_id: UUID | None = None
