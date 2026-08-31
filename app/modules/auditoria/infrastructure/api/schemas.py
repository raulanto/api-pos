from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict

_ORM = ConfigDict(from_attributes=True)


class LogAuditoriaResponse(BaseModel):
    model_config = _ORM
    id: UUID
    usuario_id: UUID
    modulo: str
    accion: str
    entidad: str
    entidad_id: str
    detalle: Optional[Any] = None
    ip_address: Optional[str] = None
    fecha: datetime
