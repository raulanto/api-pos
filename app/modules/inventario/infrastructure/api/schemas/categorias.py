from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

_ORM = ConfigDict(from_attributes=True)


"""
    Request para crear una categoría.
"""
class CrearCategoriaRequest(BaseModel):
    nombre: str = Field(min_length=1, max_length=100)
    categoria_padre_id: Optional[UUID] = None


"""
    Request para actualizar una categoría.
"""
class ActualizarCategoriaRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nombre: Optional[str] = Field(default=None, min_length=1, max_length=100)
    categoria_padre_id: Optional[UUID] = None
    cambiar_padre: bool = False


"""
    Response para una categoría.
"""
class CategoriaResponse(BaseModel):
    model_config = _ORM
    id: UUID
    nombre: str
    categoria_padre_id: Optional[UUID]
    activo: bool
