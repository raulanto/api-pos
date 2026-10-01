from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
from typing import Any


class NotificacionOut(BaseModel):
    id: UUID
    usuario_id: UUID
    sucursal_id: UUID | None = None
    modulo: str
    tipo: str
    titulo: str
    mensaje: str
    leida: bool
    fecha_leida: datetime | None = None
    entidad: str | None = None
    entidad_id: str | None = None
    datos: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    class Config:
        from_attributes = True


class ResumenNotificacionesOut(BaseModel):
    unread_count: int
