from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.shared.responses import Page

__all__ = ["FiltroAuditoria", "Page"]


@dataclass
class FiltroAuditoria:
    usuario_id: UUID | None = None
    modulo: str | None = None
    accion: str | None = None
    entidad: str | None = None
    entidad_id: str | None = None
    desde: datetime | None = None
    hasta: datetime | None = None
