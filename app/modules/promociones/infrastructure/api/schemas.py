from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.promociones.domain.entities import TipoPromocion


class ObjetivoRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    producto_id: Optional[UUID] = None
    producto_unidad_id: Optional[UUID] = None

    @model_validator(mode="after")
    def _uno_u_otro(self):
        if (self.producto_id is None) == (self.producto_unidad_id is None):
            raise ValueError("Indicá exactamente uno de `producto_id` o `producto_unidad_id`.")
        return self


class _PromocionParams(BaseModel):
    prioridad: int = Field(default=100, ge=0)
    activo: bool = True
    sucursal_id: Optional[UUID] = None
    vigente_desde: Optional[datetime] = None
    vigente_hasta: Optional[datetime] = None
    nxm_lleva: Optional[int] = Field(default=None, ge=1)
    nxm_paga: Optional[int] = Field(default=None, ge=1)
    descuento_pct: Optional[Decimal] = Field(default=None, gt=0, le=100)
    precio_fijo: Optional[Decimal] = Field(default=None, ge=0)
    cantidad_minima: Optional[Decimal] = Field(default=None, gt=0)


class CrearPromocionRequest(_PromocionParams):
    model_config = ConfigDict(extra="forbid")
    nombre: str = Field(min_length=1, max_length=120)
    tipo: TipoPromocion
    objetivos: list[ObjetivoRequest] = Field(min_length=1)

    @model_validator(mode="after")
    def _params_por_tipo(self):
        if self.tipo == TipoPromocion.NXM and (self.nxm_lleva is None or self.nxm_paga is None):
            raise ValueError("NxM requiere `nxm_lleva` y `nxm_paga`.")
        if self.tipo == TipoPromocion.NXM and not (self.nxm_lleva > self.nxm_paga):
            raise ValueError("NxM debe cumplir `nxm_lleva > nxm_paga`.")
        if self.tipo == TipoPromocion.PORCENTAJE and self.descuento_pct is None:
            raise ValueError("`porcentaje` requiere `descuento_pct`.")
        if self.tipo == TipoPromocion.PRECIO_FIJO and self.precio_fijo is None:
            raise ValueError("`precio_fijo` requiere `precio_fijo`.")
        return self


class ActualizarPromocionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nombre: Optional[str] = Field(default=None, min_length=1, max_length=120)
    prioridad: Optional[int] = Field(default=None, ge=0)
    activo: Optional[bool] = None
    tipo: Optional[TipoPromocion] = None
    sucursal_id: Optional[UUID] = None
    cambiar_sucursal: bool = False
    vigente_desde: Optional[datetime] = None
    vigente_hasta: Optional[datetime] = None
    cambiar_vigencia: bool = False
    nxm_lleva: Optional[int] = Field(default=None, ge=1)
    nxm_paga: Optional[int] = Field(default=None, ge=1)
    descuento_pct: Optional[Decimal] = Field(default=None, gt=0, le=100)
    precio_fijo: Optional[Decimal] = Field(default=None, ge=0)
    cantidad_minima: Optional[Decimal] = Field(default=None, gt=0)
    cambiar_cantidad_minima: bool = False
    objetivos: Optional[list[ObjetivoRequest]] = None


class ObjetivoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    producto_id: Optional[UUID] = None
    producto_unidad_id: Optional[UUID] = None


class PromocionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    nombre: str
    tipo: TipoPromocion
    activo: bool
    prioridad: int
    sucursal_id: Optional[UUID] = None
    vigente_desde: Optional[datetime] = None
    vigente_hasta: Optional[datetime] = None
    nxm_lleva: Optional[int] = None
    nxm_paga: Optional[int] = None
    descuento_pct: Optional[Decimal] = None
    precio_fijo: Optional[Decimal] = None
    cantidad_minima: Optional[Decimal] = None
    created_at: datetime
    objetivos: list[ObjetivoResponse] = []
