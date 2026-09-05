from datetime import date
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CrearLoteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    codigo_lote: str = Field(min_length=1, max_length=60)
    costo: Decimal = Field(ge=0)
    fecha_caducidad: Optional[date] = None
    proveedor: Optional[str] = Field(default=None, max_length=150)


class ActualizarLoteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    codigo_lote: Optional[str] = Field(default=None, min_length=1, max_length=60)
    costo: Optional[Decimal] = Field(default=None, ge=0)
    fecha_caducidad: Optional[date] = None
    cambiar_fecha_caducidad: bool = False
    proveedor: Optional[str] = Field(default=None, max_length=150)
    cambiar_proveedor: bool = False


class LoteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    producto_id: UUID
    codigo_lote: str
    fecha_caducidad: Optional[date] = None
    costo: Decimal
    proveedor: Optional[str] = None
    activo: bool


class LoteNuevoEnMovimiento(BaseModel):
    """Datos para crear un lote al vuelo dentro de una ENTRADA de `POST /movimientos`."""
    model_config = ConfigDict(extra="forbid")
    codigo_lote: str = Field(min_length=1, max_length=60)
    fecha_caducidad: Optional[date] = None
    costo: Optional[Decimal] = Field(default=None, ge=0)
    proveedor: Optional[str] = Field(default=None, max_length=150)


class LotePorVencerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    lote: LoteResponse
    sucursal_id: UUID
    cantidad: Decimal
    dias_para_vencer: Optional[int] = None
