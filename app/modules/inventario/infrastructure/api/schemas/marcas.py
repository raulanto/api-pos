from typing import ClassVar, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.shared.responses import EmbeddableModel
from app.shared.schemas.embeds import MarcaEmbed

_ORM = ConfigDict(from_attributes=True)


"""
    Request para crear una marca.
"""
class CrearMarcaRequest(BaseModel):
    nombre: str = Field(min_length=1, max_length=100)


"""
    Request para actualizar una marca.
"""
class ActualizarMarcaRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nombre: Optional[str] = Field(default=None, min_length=1, max_length=100)


"""
    Response para una marca.
"""
class MarcaResponse(EmbeddableModel):
    id: UUID
    nombre: str
    activo: bool
