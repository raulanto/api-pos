from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

_ORM = ConfigDict(from_attributes=True)


"""
    Response para una existencia.
"""
class ExistenciaResponse(BaseModel):
    model_config = _ORM
    id: UUID
    producto_id: UUID
    sucursal_id: UUID
    cantidad: Decimal
    stock_minimo: Decimal
    stock_maximo: Optional[Decimal]
    updated_at: datetime


"""
    Request para configurar umbrales.
"""
class ConfigurarUmbralesRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    stock_minimo: Decimal = Field(ge=0)
    stock_maximo: Optional[Decimal] = Field(default=None, ge=0)
