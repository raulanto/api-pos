from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.modules.agenda.domain.value_objects import EstadoCita


@dataclass
class FiltroCitas:
    sucursal_id: UUID | None = None
    servicio_id: UUID | None = None
    empleado_id: UUID | None = None
    cliente_id: UUID | None = None
    estado: EstadoCita | None = None
    desde: datetime | None = None
    hasta: datetime | None = None
