from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.ventas.domain.value_objects import MetodoPago
from app.modules.ventas.infrastructure.api.schemas import PagoRequest
from app.modules.pedidos.domain.value_objects import (
    TipoPedido, CanalPedido, EstadoPedido, EstadoEntrega,
)

_ORM = ConfigDict(from_attributes=True)
_FORBID = ConfigDict(extra="forbid")


# --------------------------------------------------------------------------- #
# Requests
# --------------------------------------------------------------------------- #
class LineaPedidoRequest(BaseModel):
    model_config = _FORBID
    producto_id: UUID
    cantidad: Decimal = Field(gt=0)
    precio_unitario: Decimal = Field(ge=0)
    descuento_linea: Decimal = Field(default=Decimal("0"), ge=0)
    impuesto_tasa: Decimal = Field(default=Decimal("0"), ge=0)
    producto_unidad_id: Optional[UUID] = None


class CrearPedidoRequest(BaseModel):
    model_config = _FORBID
    tipo: TipoPedido
    canal: CanalPedido = CanalPedido.POS
    lineas: List[LineaPedidoRequest] = Field(min_length=1)
    cliente_id: Optional[UUID] = None
    telefono: Optional[str] = Field(default=None, max_length=50)
    descuento_total: Decimal = Field(default=Decimal("0"), ge=0)
    motivo_descuento: Optional[str] = Field(default=None, max_length=255)
    costo_envio: Decimal = Field(default=Decimal("0"), ge=0)
    codigo_cupon: Optional[str] = Field(default=None, max_length=40)
    cliente_segmento: Optional[str] = Field(default=None, max_length=60)
    notas: Optional[str] = Field(default=None, max_length=1000)
    fecha_promesa: Optional[datetime] = None
    direccion_texto: Optional[str] = Field(default=None, max_length=1000)
    referencia_direccion: Optional[str] = Field(default=None, max_length=500)
    confirmar: bool = False


class ActualizarPedidoRequest(BaseModel):
    """Todo opcional. Sólo se aplican las claves presentes en el body."""
    model_config = _FORBID
    lineas: Optional[List[LineaPedidoRequest]] = Field(default=None, min_length=1)
    tipo: Optional[TipoPedido] = None       # cambiar a mostrador limpia los datos de envío
    canal: Optional[CanalPedido] = None
    cliente_id: Optional[UUID] = None
    telefono: Optional[str] = Field(default=None, max_length=50)
    descuento_total: Optional[Decimal] = Field(default=None, ge=0)
    motivo_descuento: Optional[str] = Field(default=None, max_length=255)
    costo_envio: Optional[Decimal] = Field(default=None, ge=0)
    codigo_cupon: Optional[str] = Field(default=None, max_length=40)
    cliente_segmento: Optional[str] = Field(default=None, max_length=60)
    notas: Optional[str] = Field(default=None, max_length=1000)
    fecha_promesa: Optional[datetime] = None
    direccion_texto: Optional[str] = Field(default=None, max_length=1000)
    referencia_direccion: Optional[str] = Field(default=None, max_length=500)


class CancelarPedidoRequest(BaseModel):
    model_config = _FORBID
    motivo: Optional[str] = Field(default=None, max_length=255)


class CambiarEntregaRequest(BaseModel):
    model_config = _FORBID
    estado_entrega: Optional[EstadoEntrega] = None
    repartidor_id: Optional[UUID] = None
    motivo: Optional[str] = Field(default=None, max_length=255)


class RegistrarAnticipoRequest(BaseModel):
    model_config = _FORBID
    monto: Decimal = Field(gt=0)
    metodo_pago: MetodoPago
    referencia: Optional[str] = Field(default=None, max_length=120)


class FacturarPedidoRequest(BaseModel):
    model_config = _FORBID
    caja_turno_id: UUID
    pagos: List[PagoRequest] = []
    recalcular_precios: bool = False


# --------------------------------------------------------------------------- #
# Responses
# --------------------------------------------------------------------------- #
class DetallePedidoResponse(BaseModel):
    model_config = _ORM
    id: UUID
    producto_id: UUID
    producto_unidad_id: Optional[UUID] = None
    cantidad: Decimal
    cantidad_en_unidad_base: Optional[Decimal] = None
    precio_unitario: Decimal
    descuento_linea: Decimal
    impuesto_tasa: Decimal
    promo_id: Optional[UUID] = None
    promo_etiqueta: Optional[str] = None
    promo_descuento: Decimal
    subtotal: Decimal


class PedidoPagoResponse(BaseModel):
    model_config = _ORM
    id: UUID
    monto: Decimal
    metodo_pago: MetodoPago
    referencia: Optional[str] = None
    reembolsado: bool
    created_at: datetime


class PedidoResponse(BaseModel):
    model_config = _ORM
    id: UUID
    sucursal_id: UUID
    usuario_id: UUID
    cliente_id: Optional[UUID] = None
    tipo: TipoPedido
    canal: CanalPedido
    estado: EstadoPedido
    estado_entrega: Optional[EstadoEntrega] = None
    telefono: Optional[str] = None
    descuento_total: Decimal
    motivo_descuento: Optional[str] = None
    costo_envio: Decimal
    codigo_cupon: Optional[str] = None
    cliente_segmento: Optional[str] = None
    notas: Optional[str] = None
    fecha_promesa: Optional[datetime] = None
    direccion_texto: Optional[str] = None
    referencia_direccion: Optional[str] = None
    repartidor_id: Optional[UUID] = None
    entrega_fallo_motivo: Optional[str] = None
    despachado_en: Optional[datetime] = None
    entregado_en: Optional[datetime] = None
    venta_id: Optional[UUID] = None
    created_at: datetime
    # Calculados
    subtotal: Decimal
    total: Decimal
    total_promociones: Decimal
    total_anticipos: Decimal
    saldo_por_cobrar: Decimal
    lineas: List[DetallePedidoResponse]
    pagos: List[PedidoPagoResponse]


class PedidoListItem(BaseModel):
    model_config = _ORM
    id: UUID
    sucursal_id: UUID
    cliente_id: Optional[UUID] = None
    tipo: TipoPedido
    canal: CanalPedido
    estado: EstadoPedido
    estado_entrega: Optional[EstadoEntrega] = None
    telefono: Optional[str] = None
    repartidor_id: Optional[UUID] = None
    total: Decimal
    saldo_por_cobrar: Decimal
    fecha_promesa: Optional[datetime] = None
    venta_id: Optional[UUID] = None
    created_at: datetime


class ResumenPedidosResponse(BaseModel):
    por_estado: dict[str, int]
    por_estado_entrega: dict[str, int]
