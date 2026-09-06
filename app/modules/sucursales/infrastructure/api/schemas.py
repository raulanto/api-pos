from datetime import datetime, time
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.modules.sucursales.domain.entities import TipoSucursal


class CrearSucursalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nombre: str = Field(min_length=1, max_length=100)
    direccion: str = Field(min_length=1, max_length=255)
    telefono: str = Field(min_length=1, max_length=20)
    tipo: TipoSucursal = TipoSucursal.TIENDA
    codigo: Optional[str] = Field(default=None, min_length=1, max_length=20)
    descripcion: Optional[str] = None
    colonia: Optional[str] = Field(default=None, max_length=100)
    ciudad: Optional[str] = Field(default=None, max_length=100)
    estado: Optional[str] = Field(default=None, max_length=100)
    codigo_postal: Optional[str] = Field(default=None, max_length=10)
    pais: Optional[str] = Field(default="México", max_length=60)
    latitud: Optional[Decimal] = Field(default=None, ge=-90, le=90)
    longitud: Optional[Decimal] = Field(default=None, ge=-180, le=180)
    email: Optional[EmailStr] = None
    horario_apertura: Optional[time] = None
    horario_cierre: Optional[time] = None
    sucursal_padre_id: Optional[UUID] = None
    permite_ventas: bool = True


class ActualizarSucursalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nombre: Optional[str] = Field(default=None, min_length=1, max_length=100)
    direccion: Optional[str] = Field(default=None, min_length=1, max_length=255)
    telefono: Optional[str] = Field(default=None, min_length=1, max_length=20)
    tipo: Optional[TipoSucursal] = None
    permite_ventas: Optional[bool] = None
    # Opcionales nulleables: mandá el flag `cambiar_*` para ponerlos en null.
    codigo: Optional[str] = Field(default=None, min_length=1, max_length=20)
    cambiar_codigo: bool = False
    descripcion: Optional[str] = None
    cambiar_descripcion: bool = False
    colonia: Optional[str] = Field(default=None, max_length=100)
    cambiar_colonia: bool = False
    ciudad: Optional[str] = Field(default=None, max_length=100)
    cambiar_ciudad: bool = False
    estado: Optional[str] = Field(default=None, max_length=100)
    cambiar_estado: bool = False
    codigo_postal: Optional[str] = Field(default=None, max_length=10)
    cambiar_codigo_postal: bool = False
    pais: Optional[str] = Field(default=None, max_length=60)
    cambiar_pais: bool = False
    latitud: Optional[Decimal] = Field(default=None, ge=-90, le=90)
    longitud: Optional[Decimal] = Field(default=None, ge=-180, le=180)
    cambiar_geo: bool = False
    email: Optional[EmailStr] = None
    cambiar_email: bool = False
    horario_apertura: Optional[time] = None
    horario_cierre: Optional[time] = None
    cambiar_horario: bool = False
    sucursal_padre_id: Optional[UUID] = None
    cambiar_padre: bool = False


class SucursalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    codigo: Optional[str] = None
    nombre: str
    tipo: TipoSucursal
    descripcion: Optional[str] = None
    direccion: str
    colonia: Optional[str] = None
    ciudad: Optional[str] = None
    estado: Optional[str] = None
    codigo_postal: Optional[str] = None
    pais: Optional[str] = None
    latitud: Optional[Decimal] = None
    longitud: Optional[Decimal] = None
    telefono: str
    email: Optional[str] = None
    horario_apertura: Optional[time] = None
    horario_cierre: Optional[time] = None
    sucursal_padre_id: Optional[UUID] = None
    permite_ventas: bool
    activo: bool
    created_at: datetime
    # Fachada: `key` estable + `url` prefirmada (derivada, no se persiste).
    imagen_fachada_key: Optional[str] = None
    imagen_fachada_url: Optional[str] = None
