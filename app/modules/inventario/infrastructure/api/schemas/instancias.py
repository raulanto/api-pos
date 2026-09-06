from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.inventario.domain.value_objects import EstadoInstancia


class AbrirInstanciaRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # Sucursal del envase. Un rol de sucursal queda acotado a la suya.
    sucursal_id: Optional[UUID] = None
    # Capacidad: una presentación (capacidad = su factor) XOR un valor manual.
    producto_unidad_id: Optional[UUID] = None
    capacidad: Optional[Decimal] = Field(default=None, gt=0)
    lote_id: Optional[UUID] = None
    motivo: Optional[str] = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def _capacidad_xor(self) -> "AbrirInstanciaRequest":
        if self.producto_unidad_id is not None and self.capacidad is not None:
            raise ValueError(
                "Indicá `producto_unidad_id` O `capacidad`, no ambos."
            )
        return self


class ConsumirInstanciaRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cantidad: Decimal = Field(gt=0)
    motivo: Optional[str] = Field(default=None, max_length=255)


class MermarInstanciaRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cantidad: Decimal = Field(gt=0)
    motivo: Optional[str] = Field(default=None, max_length=255)


class AjustarInstanciaRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    saldo_medido: Decimal = Field(ge=0)
    motivo: Optional[str] = Field(default=None, max_length=255)


class DescartarInstanciaRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    motivo: str = Field(min_length=1, max_length=255)


class InstanciaResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    producto_id: UUID
    sucursal_id: UUID
    producto_unidad_id: Optional[UUID] = None
    lote_id: Optional[UUID] = None
    capacidad_inicial: Decimal
    saldo: Decimal
    estado: EstadoInstancia
    abierta_por: UUID
    abierta_at: datetime
    cerrada_at: Optional[datetime] = None
    motivo_cierre: Optional[str] = None
