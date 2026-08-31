from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.inventario.domain.value_objects import TipoMovimiento

_ORM = ConfigDict(from_attributes=True)


# --------------------------------------------------------------------------- #
# Categorías
# --------------------------------------------------------------------------- #
class CrearCategoriaRequest(BaseModel):
    nombre: str = Field(min_length=1, max_length=100)
    categoria_padre_id: Optional[UUID] = None


class ActualizarCategoriaRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nombre: Optional[str] = Field(default=None, min_length=1, max_length=100)
    # Enviar la clave explícitamente (incluso en null) para reasignar/limpiar el padre.
    categoria_padre_id: Optional[UUID] = None
    cambiar_padre: bool = False


class CategoriaResponse(BaseModel):
    model_config = _ORM
    id: UUID
    nombre: str
    categoria_padre_id: Optional[UUID]
    activo: bool


# --------------------------------------------------------------------------- #
# Productos
# --------------------------------------------------------------------------- #
class CrearProductoRequest(BaseModel):
    sku: str = Field(min_length=1, max_length=50)
    nombre: str = Field(min_length=1, max_length=150)
    categoria_id: UUID
    unidad_medida: str = Field(min_length=1, max_length=20)
    precio_venta: Decimal = Field(ge=0)
    costo: Decimal = Field(ge=0)
    impuesto_tasa: Decimal = Field(ge=0)
    permite_stock_negativo: bool = False
    codigo_barras: Optional[str] = Field(default=None, max_length=50)
    descripcion: Optional[str] = None


class ActualizarProductoRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nombre: Optional[str] = Field(default=None, min_length=1, max_length=150)
    descripcion: Optional[str] = None
    categoria_id: Optional[UUID] = None
    unidad_medida: Optional[str] = Field(default=None, min_length=1, max_length=20)
    precio_venta: Optional[Decimal] = Field(default=None, ge=0)
    costo: Optional[Decimal] = Field(default=None, ge=0)
    impuesto_tasa: Optional[Decimal] = Field(default=None, ge=0)
    permite_stock_negativo: Optional[bool] = None
    codigo_barras: Optional[str] = Field(default=None, max_length=50)
    cambiar_codigo_barras: bool = False


class ProductoResponse(BaseModel):
    model_config = _ORM
    id: UUID
    sku: str
    codigo_barras: Optional[str]
    nombre: str
    descripcion: Optional[str]
    categoria_id: UUID
    unidad_medida: str
    precio_venta: Decimal
    costo: Decimal
    impuesto_tasa: Decimal
    permite_stock_negativo: bool
    activo: bool


class ProductosPaginados(BaseModel):
    items: list[ProductoResponse]
    total: int
    limit: int
    offset: int


# --------------------------------------------------------------------------- #
# Existencias
# --------------------------------------------------------------------------- #
class ExistenciaResponse(BaseModel):
    model_config = _ORM
    id: UUID
    producto_id: UUID
    sucursal_id: UUID
    cantidad: Decimal
    stock_minimo: Decimal
    stock_maximo: Optional[Decimal]
    updated_at: datetime


class ConfigurarUmbralesRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    stock_minimo: Decimal = Field(ge=0)
    stock_maximo: Optional[Decimal] = Field(default=None, ge=0)


# --------------------------------------------------------------------------- #
# Movimientos
# --------------------------------------------------------------------------- #
class AplicarMovimientoRequest(BaseModel):
    producto_id: UUID
    tipo: TipoMovimiento
    cantidad: Optional[Decimal] = Field(default=None, gt=0)
    cantidad_final: Optional[Decimal] = Field(default=None, ge=0)
    referencia_tipo: str = Field(min_length=1, max_length=20)
    referencia_id: Optional[UUID] = None
    costo_unitario: Optional[Decimal] = Field(default=None, ge=0)
    motivo: Optional[str] = Field(default=None, max_length=255)
    stock_minimo: Optional[Decimal] = Field(default=None, ge=0)
    stock_maximo: Optional[Decimal] = Field(default=None, ge=0)


class TransferenciaRequest(BaseModel):
    producto_id: UUID
    sucursal_origen_id: UUID
    sucursal_destino_id: UUID
    cantidad: Decimal = Field(gt=0)
    referencia_id: Optional[UUID] = None
    costo_unitario: Optional[Decimal] = Field(default=None, ge=0)
    motivo: Optional[str] = Field(default=None, max_length=255)


class MovimientoResponse(BaseModel):
    model_config = _ORM
    id: UUID
    producto_id: UUID
    sucursal_id: UUID
    tipo: TipoMovimiento
    cantidad: Decimal
    costo_unitario: Optional[Decimal]
    referencia_tipo: str
    referencia_id: Optional[UUID]
    usuario_id: UUID
    motivo: Optional[str]
    created_at: datetime


class MovimientosPaginados(BaseModel):
    items: list[MovimientoResponse]
    total: int
    limit: int
    offset: int
