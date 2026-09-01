from typing import ClassVar, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.shared.responses import EmbeddableModel
from app.shared.schemas.embeds import CategoriaEmbed

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
class CategoriaResponse(EmbeddableModel):
    _embed_fields: ClassVar[tuple[str, ...]] = ("padre",)
    id: UUID
    nombre: str
    categoria_padre_id: Optional[UUID]
    activo: bool
    # Embebida (?include=padre)
    padre: Optional[CategoriaEmbed] = None
