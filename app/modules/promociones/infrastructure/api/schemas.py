from datetime import datetime, time
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.promociones.domain.entities import TipoPromocion


class ObjetivoRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    producto_id: Optional[UUID] = None
    producto_unidad_id: Optional[UUID] = None
    categoria_id: Optional[UUID] = None

    @model_validator(mode="after")
    def _uno_de_tres(self):
        puestos = sum(
            x is not None for x in (self.producto_id, self.producto_unidad_id, self.categoria_id)
        )
        if puestos != 1:
            raise ValueError(
                "Indicá exactamente uno de `producto_id`, `producto_unidad_id` o `categoria_id`."
            )
        return self


class _PromocionParams(BaseModel):
    prioridad: int = Field(default=100, ge=0)
    activo: bool = True
    # Apilado: False (default) = exclusiva por línea; True = se apila sobre el residual.
    combinable: bool = False
    tope_descuento: Optional[Decimal] = Field(default=None, ge=0)
    monto_minimo_compra: Optional[Decimal] = Field(default=None, ge=0)
    # Condiciones: sólo aplica con ese método de pago / segmento de cliente,
    # o sólo con un cupón válido.
    metodo_pago_requerido: Optional[str] = Field(default=None, max_length=20)
    cliente_segmento: Optional[str] = Field(default=None, max_length=30)
    requiere_cupon: bool = False
    # Sucursales donde aplica; lista vacía = todas.
    sucursales: list[UUID] = []
    vigente_desde: Optional[datetime] = None
    vigente_hasta: Optional[datetime] = None
    # Ventana horaria (hora local, `APP_TIMEZONE`) y días. `dias_semana` = bitmask
    # lun..dom = bit 0..6 (ej. lun+mié+vie = 1|4|16 = 21).
    hora_desde: Optional[time] = None
    hora_hasta: Optional[time] = None
    dias_semana: Optional[int] = Field(default=None, ge=1, le=127)
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
    combinable: Optional[bool] = None
    tope_descuento: Optional[Decimal] = Field(default=None, ge=0)
    monto_minimo_compra: Optional[Decimal] = Field(default=None, ge=0)
    # Mandar `cambiar_topes=true` para fijar/limpiar `tope_descuento` + `monto_minimo_compra`.
    cambiar_topes: bool = False
    metodo_pago_requerido: Optional[str] = Field(default=None, max_length=20)
    cliente_segmento: Optional[str] = Field(default=None, max_length=30)
    requiere_cupon: Optional[bool] = None
    cambiar_condiciones: bool = False
    sucursales: Optional[list[UUID]] = None
    cambiar_sucursales: bool = False
    vigente_desde: Optional[datetime] = None
    vigente_hasta: Optional[datetime] = None
    cambiar_vigencia: bool = False
    hora_desde: Optional[time] = None
    hora_hasta: Optional[time] = None
    dias_semana: Optional[int] = Field(default=None, ge=1, le=127)
    cambiar_horario: bool = False
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
    categoria_id: Optional[UUID] = None


class PromocionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    nombre: str
    tipo: TipoPromocion
    activo: bool
    prioridad: int
    combinable: bool
    tope_descuento: Optional[Decimal] = None
    monto_minimo_compra: Optional[Decimal] = None
    metodo_pago_requerido: Optional[str] = None
    cliente_segmento: Optional[str] = None
    requiere_cupon: bool = False
    sucursales: list[UUID] = []
    vigente_desde: Optional[datetime] = None
    vigente_hasta: Optional[datetime] = None
    hora_desde: Optional[time] = None
    hora_hasta: Optional[time] = None
    dias_semana: Optional[int] = None
    nxm_lleva: Optional[int] = None
    nxm_paga: Optional[int] = None
    descuento_pct: Optional[Decimal] = None
    precio_fijo: Optional[Decimal] = None
    cantidad_minima: Optional[Decimal] = None
    created_at: datetime
    objetivos: list[ObjetivoResponse] = []
