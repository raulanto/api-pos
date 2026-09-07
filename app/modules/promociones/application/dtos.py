from dataclasses import dataclass
from uuid import UUID

from app.modules.promociones.domain.entities import TipoPromocion


@dataclass
class FiltroPromociones:
    activo: bool | None = None
    tipo: TipoPromocion | None = None
    sucursal_id: UUID | None = None
    busqueda: str | None = None   # coincide contra `nombre`
