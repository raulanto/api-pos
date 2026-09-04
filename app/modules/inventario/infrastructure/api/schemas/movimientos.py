from datetime import datetime
from decimal import Decimal
from typing import ClassVar, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.inventario.domain.value_objects import TipoMovimiento
from app.shared.responses import EmbeddableModel
from app.shared.schemas.embeds import ProductoEmbed, UsuarioEmbed

_ORM = ConfigDict(from_attributes=True)


"""
    Request para aplicar un movimiento.
"""
class AplicarMovimientoRequest(BaseModel):
    producto_id: UUID
    sucursal_id: UUID
    tipo: TipoMovimiento
    cantidad: Optional[Decimal] = Field(default=None, gt=0)
    cantidad_final: Optional[Decimal] = Field(default=None, ge=0)
    referencia_tipo: str = Field(min_length=1, max_length=20)
    referencia_id: Optional[UUID] = None
    costo_unitario: Optional[Decimal] = Field(default=None, ge=0)
    motivo: Optional[str] = Field(default=None, max_length=255)
    stock_minimo: Optional[Decimal] = Field(default=None, ge=0)
    stock_maximo: Optional[Decimal] = Field(default=None, ge=0)
    # Precios volátiles (opcional): empujar costo/precio al producto.
    actualizar_costo: bool = False                       # ENTRADA + costo_unitario
    nuevo_precio_venta: Optional[Decimal] = Field(default=None, ge=0)


"""
    Request para transferir un producto.
"""
class TransferenciaRequest(BaseModel):
    producto_id: UUID
    sucursal_origen_id: UUID
    sucursal_destino_id: UUID
    cantidad: Decimal = Field(gt=0)
    referencia_id: Optional[UUID] = None
    costo_unitario: Optional[Decimal] = Field(default=None, ge=0)
    motivo: Optional[str] = Field(default=None, max_length=255)


"""
    Response para un movimiento.
"""
class MovimientoResponse(EmbeddableModel):
    _embed_fields: ClassVar[tuple[str, ...]] = ("producto", "usuario")
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
    # Embebidas (?include=producto,usuario)
    producto: Optional[ProductoEmbed] = None
    usuario: Optional[UsuarioEmbed] = None

