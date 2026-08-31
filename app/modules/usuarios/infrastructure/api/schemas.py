from pydantic import BaseModel, EmailStr
from uuid import UUID

class CrearUsuarioRequest(BaseModel):
    sucursal_id: UUID | None = None
    rol_id: UUID
    nombre: str
    email: EmailStr
    password: str

class UsuarioResponse(BaseModel):
    id: UUID
    sucursal_id: UUID | None
    rol_id: UUID
    nombre: str
    email: str
    activo: bool

    class Config:
        from_attributes = True

class LoginRequest(BaseModel):
    email: EmailStr
    password: str
