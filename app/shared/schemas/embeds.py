"""DTOs mínimos (solo columnas escalares) para relaciones embebidas vía `?include=`.

Se mantienen chicos a propósito: no arrastran sub-relaciones, así que
serializarlos desde un objeto ORM ya cargado no dispara lazy-loading.
Viven en `shared` porque los comparten varios módulos (p. ej. UsuarioEmbed lo
usan ventas, inventario y auditoría).
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict

_ORM = ConfigDict(from_attributes=True)


class UsuarioEmbed(BaseModel):
    model_config = _ORM
    id: UUID
    nombre: str
    email: str
    rol_id: UUID
    sucursal_id: Optional[UUID] = None
    activo: bool


class SucursalEmbed(BaseModel):
    model_config = _ORM
    id: UUID
    nombre: str
    direccion: str
    telefono: str
    activo: bool


class ClienteEmbed(BaseModel):
    model_config = _ORM
    id: UUID
    sucursal_id: UUID
    nombre: str
    email: Optional[str] = None
    telefono: Optional[str] = None
    limite_credito: Decimal
    saldo_credito: Decimal
    activo: bool


class CajaTurnoEmbed(BaseModel):
    model_config = _ORM
    id: UUID
    sucursal_id: UUID
    usuario_id: UUID
    estado: str
    abierto_en: datetime
    cerrado_en: Optional[datetime] = None


class CategoriaEmbed(BaseModel):
    model_config = _ORM
    id: UUID
    nombre: str
    categoria_padre_id: Optional[UUID] = None
    activo: bool


class ProductoEmbed(BaseModel):
    model_config = _ORM
    id: UUID
    sku: str
    nombre: str
    categoria_id: UUID
    precio_venta: Decimal
    activo: bool


class ExistenciaEmbed(BaseModel):
    model_config = _ORM
    id: UUID
    producto_id: UUID
    sucursal_id: UUID
    cantidad: Decimal
    stock_minimo: Decimal
    stock_maximo: Optional[Decimal] = None
