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


# --------------------------------------------------------------------------- #
# Desglose de stock por presentación (GET /productos/{id}/existencias)
# --------------------------------------------------------------------------- #
class DesglosePresentacionResponse(BaseModel):
    model_config = _ORM
    producto_unidad_id: Optional[UUID] = None   # None = unidad base
    nombre: str
    factor: Decimal
    cantidad: Decimal          # cantidad_base / factor (ej: 8.8750 rejas -> 71 botellas)
    cantidad_entera: int       # floor(cantidad): presentaciones completas


class DesgloseSucursalResponse(BaseModel):
    model_config = _ORM
    sucursal_id: UUID
    cantidad_base: Decimal
    stock_minimo: Decimal
    stock_maximo: Optional[Decimal] = None
    presentaciones: list[DesglosePresentacionResponse]


class DesgloseStockResponse(BaseModel):
    model_config = _ORM
    producto_id: UUID
    unidad_base: str
    cantidad_base_global: Decimal
    presentaciones_global: list[DesglosePresentacionResponse]
    por_sucursal: list[DesgloseSucursalResponse]
