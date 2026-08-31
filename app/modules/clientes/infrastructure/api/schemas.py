from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

_ORM = ConfigDict(from_attributes=True)


class CrearClienteRequest(BaseModel):
    nombre: str = Field(min_length=1, max_length=150)
    email: Optional[EmailStr] = None
    telefono: Optional[str] = Field(default=None, max_length=50)
    rfc_identificacion: Optional[str] = Field(default=None, max_length=50)
    limite_credito: Decimal = Field(default=Decimal("0"), ge=0)


class ActualizarClienteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nombre: Optional[str] = Field(default=None, min_length=1, max_length=150)
    # Enviá la clave explícitamente (incluso en null) para cambiar/limpiar el email.
    email: Optional[EmailStr] = None
    cambiar_email: bool = False
    telefono: Optional[str] = Field(default=None, max_length=50)
    rfc_identificacion: Optional[str] = Field(default=None, max_length=50)


class AbonarClienteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    monto: Decimal = Field(gt=0)


class CambiarLimiteCreditoRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    limite_credito: Decimal = Field(ge=0)


class ClienteResponse(BaseModel):
    model_config = _ORM
    id: UUID
    sucursal_id: UUID
    nombre: str
    email: Optional[str]
    telefono: Optional[str]
    rfc_identificacion: Optional[str]
    limite_credito: Decimal
    saldo_credito: Decimal
    activo: bool
    created_at: datetime


