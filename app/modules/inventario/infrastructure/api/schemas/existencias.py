from datetime import datetime
from decimal import Decimal
from typing import ClassVar, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.shared.responses import EmbeddableModel
from app.shared.schemas.embeds import ProductoEmbed

_ORM = ConfigDict(from_attributes=True)


"""
    Response para una existencia.
"""
class ExistenciaResponse(EmbeddableModel):
    _embed_fields: ClassVar[tuple[str, ...]] = ("producto",)
    id: UUID
    producto_id: UUID
    sucursal_id: UUID
    cantidad: Decimal
    stock_minimo: Decimal
    stock_maximo: Optional[Decimal]
    updated_at: datetime
    # Embebida (?include=producto)
    producto: Optional[ProductoEmbed] = None


"""
    Request para configurar umbrales.
"""
class ConfigurarUmbralesRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    stock_minimo: Decimal = Field(ge=0)
    stock_maximo: Optional[Decimal] = Field(default=None, ge=0)
