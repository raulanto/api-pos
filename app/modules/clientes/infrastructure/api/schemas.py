from pydantic import BaseModel, EmailStr
from typing import Optional
from uuid import UUID
from decimal import Decimal

class CrearClienteRequest(BaseModel):
    nombre: str
    email: Optional[EmailStr] = None
    telefono: Optional[str] = None
    rfc_identificacion: Optional[str] = None
    limite_credito: Decimal = Decimal("0")

class ClienteResponse(BaseModel):
    id: UUID
    sucursal_id: UUID
    nombre: str
    email: Optional[str]
    telefono: Optional[str]
    rfc_identificacion: Optional[str]
    limite_credito: Decimal
    saldo_credito: Decimal
    activo: bool
