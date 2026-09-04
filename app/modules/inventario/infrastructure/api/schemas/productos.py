from decimal import Decimal
from typing import ClassVar, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.inventario.domain.value_objects import TipoProducto
from app.shared.responses import EmbeddableModel
from app.shared.schemas.embeds import (
    CategoriaEmbed, ComponenteEmbed, ExistenciaEmbed, ProductoEmbed, UnidadEmbed,
)

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
    sku: Optional[str] = Field(default=None, min_length=1, max_length=50)
    nombre: Optional[str] = Field(default=None, min_length=1, max_length=150)
    descripcion: Optional[str] = None
    categoria_id: Optional[UUID] = None
    unidad_medida: Optional[str] = Field(default=None, min_length=1, max_length=20)
    precio_venta: Optional[Decimal] = Field(default=None, ge=0)
    costo: Optional[Decimal] = Field(default=None, ge=0)
    impuesto_tasa: Optional[Decimal] = Field(default=None, ge=0)
    tipo: Optional[TipoProducto] = None
    permite_stock_negativo: Optional[bool] = None
    codigo_barras: Optional[str] = Field(default=None, max_length=50)
    cambiar_codigo_barras: bool = False
    # Para dejar `descripcion` en NULL hay que mandarlo explícitamente.
    cambiar_descripcion: bool = False

"""
    Response de KPIs del catálogo de productos (GET /productos/kpis).
"""
class ProductoKpisResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    total: int
    activos: int
    inactivos: int
    por_tipo: dict[str, int]
    con_codigo_barras: int
    sin_codigo_barras: int
    categorias_distintas: int
    precio_venta_min: Optional[Decimal]
    precio_venta_max: Optional[Decimal]
    precio_venta_promedio: Optional[Decimal]
    costo_min: Optional[Decimal]
    costo_max: Optional[Decimal]
    costo_promedio: Optional[Decimal]
    margen_promedio: Optional[Decimal]
    unidades_en_stock: Decimal
    valor_inventario_costo: Decimal
    valor_inventario_venta: Decimal
    productos_con_existencia: int
    productos_sin_existencia: int
    bajo_stock: int


"""
    Response para un producto.
"""
class ProductoResponse(EmbeddableModel):
    _embed_fields: ClassVar[tuple[str, ...]] = (
        "categoria", "existencias", "componentes", "unidades",
    )
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
    tipo: TipoProducto
    permite_stock_negativo: bool
    activo: bool
    # Embebidas (?include=categoria,existencias,componentes,unidades)
    categoria: Optional[CategoriaEmbed] = None
    existencias: Optional[list[ExistenciaEmbed]] = None
    componentes: Optional[list[ComponenteEmbed]] = None
    unidades: Optional[list[UnidadEmbed]] = None


# --------------------------------------------------------------------------- #
# Receta de kit (producto_componente)
# --------------------------------------------------------------------------- #
class AgregarComponenteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    producto_componente_id: UUID
    cantidad: Decimal = Field(gt=0)


class ActualizarComponenteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cantidad: Decimal = Field(gt=0)


class _LineaRecetaRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    producto_componente_id: UUID
    cantidad: Decimal = Field(gt=0)


class ReemplazarRecetaRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    componentes: list[_LineaRecetaRequest]


class ComponenteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    producto_kit_id: UUID
    producto_componente_id: UUID
    cantidad: Decimal
    producto: Optional[ProductoEmbed] = None


# --------------------------------------------------------------------------- #
# Presentaciones de venta (producto_unidad)
# --------------------------------------------------------------------------- #
class AgregarUnidadRequest(BaseModel):
    """`factor` = unidades base por 1 presentación (Reja x24 => 24).
    `unidades_por_base` = su recíproco (6 latas por reja => 6). Indicá uno."""
    model_config = ConfigDict(extra="forbid")
    nombre: str = Field(min_length=1, max_length=50)
    unidad_medida: str = Field(min_length=1, max_length=20)
    precio_venta: Decimal = Field(ge=0)
    factor: Optional[Decimal] = Field(default=None, gt=0)
    unidades_por_base: Optional[Decimal] = Field(default=None, gt=0)
    codigo_barras: Optional[str] = Field(default=None, max_length=50)


class ActualizarUnidadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nombre: Optional[str] = Field(default=None, min_length=1, max_length=50)
    unidad_medida: Optional[str] = Field(default=None, min_length=1, max_length=20)
    factor: Optional[Decimal] = Field(default=None, gt=0)
    unidades_por_base: Optional[Decimal] = Field(default=None, gt=0)
    precio_venta: Optional[Decimal] = Field(default=None, ge=0)
    codigo_barras: Optional[str] = Field(default=None, max_length=50)
    cambiar_codigo_barras: bool = False


class UnidadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    producto_id: UUID
    nombre: str
    unidad_medida: str
    factor: Decimal
    unidades_por_base: Optional[Decimal] = None
    precio_venta: Decimal
    codigo_barras: Optional[str]
    activo: bool


class ResolucionCodigoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    producto_id: UUID
    unidad_id: Optional[UUID]
    nombre_unidad: str
    unidad_medida: str
    factor: Decimal
    precio_venta: Decimal

