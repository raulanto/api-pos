from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.inventario.domain.value_objects import TipoMagnitud


class CrearUnidadMedidaRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    codigo: str = Field(min_length=1, max_length=20)
    nombre: str = Field(min_length=1, max_length=60)
    tipo_magnitud: TipoMagnitud
    decimales: int = Field(default=0, ge=0, le=6)


class ActualizarUnidadMedidaRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nombre: Optional[str] = Field(default=None, min_length=1, max_length=60)
    tipo_magnitud: Optional[TipoMagnitud] = None
    decimales: Optional[int] = Field(default=None, ge=0, le=6)


class UnidadMedidaResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    codigo: str
    nombre: str
    tipo_magnitud: TipoMagnitud
    decimales: int
    activo: bool
