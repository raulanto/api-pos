from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.modules.usuarios.domain.password_policy import LONGITUD_MINIMA


# --------------------------------------------------------------------------- #
# Usuarios
# --------------------------------------------------------------------------- #
class CrearUsuarioRequest(BaseModel):
    sucursal_id: UUID | None = None
    rol_id: UUID
    nombre: str = Field(min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(min_length=LONGITUD_MINIMA, max_length=128)

    @field_validator("password")
    @classmethod
    def _password_distinta_del_email(cls, v: str, info):
        email = info.data.get("email")
        if email and v.strip().lower() == str(email).strip().lower():
            raise ValueError("La contraseña no puede ser igual al email")
        return v


class EditarUsuarioRequest(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=100)
    email: EmailStr | None = None
    # sucursal: campo opcional; para dejarlo en null hay que enviarlo explícitamente
    sucursal_id: UUID | None = None
    model_config = {"extra": "forbid"}


class CambiarRolRequest(BaseModel):
    rol_id: UUID


class CambiarPasswordRequest(BaseModel):
    password_actual: str | None = None
    password_nueva: str = Field(min_length=LONGITUD_MINIMA, max_length=128)


class UsuarioResponse(BaseModel):
    id: UUID
    sucursal_id: UUID | None
    rol_id: UUID
    nombre: str
    email: str
    activo: bool
    last_login_at: datetime | None = None

    class Config:
        from_attributes = True


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


# --------------------------------------------------------------------------- #
# Roles / permisos
# --------------------------------------------------------------------------- #
class PermisoResponse(BaseModel):
    id: UUID
    codigo: str
    descripcion: str

    class Config:
        from_attributes = True


class RolResponse(BaseModel):
    id: UUID
    codigo: str | None
    nombre: str
    descripcion: str
    permisos: list[PermisoResponse] = []

    class Config:
        from_attributes = True


class CrearRolRequest(BaseModel):
    codigo: str = Field(min_length=1, max_length=50)
    nombre: str = Field(min_length=1, max_length=50)
    descripcion: str = Field(default="", max_length=255)
    permiso_ids: list[UUID] = []


class EditarRolRequest(BaseModel):
    nombre: str = Field(min_length=1, max_length=50)
    descripcion: str = Field(default="", max_length=255)
    model_config = {"extra": "forbid"}


class AsignarPermisosRequest(BaseModel):
    permiso_ids: list[UUID] = Field(min_length=1)
