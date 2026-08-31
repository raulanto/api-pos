from pydantic import BaseModel, Field
from uuid import UUID
from decimal import Decimal
from typing import Optional
from app.modules.inventario.domain.value_objects import TipoMovimiento

class CrearCategoriaRequest(BaseModel):
    nombre: str
    categoria_padre_id: Optional[UUID] = None

class CategoriaResponse(BaseModel):
    id: UUID
    nombre: str
    categoria_padre_id: Optional[UUID]
    activo: bool

class CrearProductoRequest(BaseModel):
    sku: str
    nombre: str
    categoria_id: UUID
    unidad_medida: str
    precio_venta: Decimal
    costo: Decimal
    impuesto_tasa: Decimal
    permite_stock_negativo: bool = False
    codigo_barras: Optional[str] = None
    descripcion: Optional[str] = None

class ProductoResponse(BaseModel):
    id: UUID
    sku: str
    nombre: str
    categoria_id: UUID
    precio_venta: Decimal
    costo: Decimal
    permite_stock_negativo: bool
    activo: bool

class AplicarMovimientoRequest(BaseModel):
    producto_id: UUID
    tipo: TipoMovimiento
    cantidad: Decimal = Field(..., gt=0)
    referencia_tipo: str
    referencia_id: Optional[UUID] = None
    costo_unitario: Optional[Decimal] = None
    motivo: Optional[str] = None
