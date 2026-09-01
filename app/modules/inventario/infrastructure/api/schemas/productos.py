from decimal import Decimal
from typing import ClassVar, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.shared.responses import EmbeddableModel
from app.shared.schemas.embeds import CategoriaEmbed, ExistenciaEmbed

_ORM = ConfigDict(from_attributes=True)

"""
    Request para crear un producto.
"""
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


"""
    Request para actualizar un producto.
"""
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

"""
    Response para un producto.
"""
class ProductoResponse(EmbeddableModel):
    _embed_fields: ClassVar[tuple[str, ...]] = ("categoria", "existencias")
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
    # Embebidas (?include=categoria,existencias)
    categoria: Optional[CategoriaEmbed] = None
    existencias: Optional[list[ExistenciaEmbed]] = None

