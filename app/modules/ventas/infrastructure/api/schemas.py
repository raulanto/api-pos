from datetime import datetime
from decimal import Decimal
from typing import ClassVar, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.ventas.domain.value_objects import MetodoPago, EstadoVenta, MetodoDevolucion
from app.shared.responses import EmbeddableModel
from app.shared.schemas.embeds import ClienteEmbed, UsuarioEmbed, CajaTurnoEmbed

_ORM = ConfigDict(from_attributes=True)


# --------------------------------------------------------------------------- #
# Ventas
# --------------------------------------------------------------------------- #
class LineaVentaRequest(BaseModel):
    producto_id: UUID
    cantidad: Decimal = Field(gt=0)
    precio_unitario: Decimal = Field(ge=0)
    descuento_linea: Decimal = Field(default=Decimal("0"), ge=0)
    impuesto_tasa: Decimal = Field(default=Decimal("0"), ge=0)
    # Presentación vendida (producto_unidad). Omitir = unidad base.
    producto_unidad_id: Optional[UUID] = None


class PagoRequest(BaseModel):
    monto: Decimal = Field(gt=0)
    metodo_pago: MetodoPago
    # Sólo efectivo: con cuánto pagó el cliente. Si viene, debe ser >= monto.
    monto_recibido: Optional[Decimal] = Field(default=None, gt=0)


class CrearVentaRequest(BaseModel):
    caja_turno_id: UUID
    cliente_id: Optional[UUID] = None
    descuento_total: Decimal = Field(default=Decimal("0"), ge=0)
    lineas: List[LineaVentaRequest]
    pagos: List[PagoRequest]


class CotizarVentaRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    descuento_total: Decimal = Field(default=Decimal("0"), ge=0)
    lineas: List[LineaVentaRequest]


class CotizacionLineaResponse(BaseModel):
    model_config = _ORM
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
    stock_disponible: Optional[Decimal] = None   # en la unidad de la línea; None = ilimitado
    hay_stock: bool


class CotizacionResponse(BaseModel):
    model_config = _ORM
    lineas: List[CotizacionLineaResponse]
    descuento_total: Decimal
    total_promociones: Decimal
    total: Decimal


class AnularVentaRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    motivo: Optional[str] = Field(default=None, max_length=255)


class DevolverVentaLineaRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    detalle_venta_id: UUID
    cantidad: Decimal = Field(gt=0)


class DevolverVentaRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    caja_turno_id: UUID
    metodo_devolucion: MetodoDevolucion
    lineas: List[DevolverVentaLineaRequest] = Field(min_length=1)
    motivo: Optional[str] = Field(default=None, max_length=255)


class DevolucionLineaResponse(BaseModel):
    model_config = _ORM
    id: UUID
    detalle_venta_id: UUID
    cantidad: Decimal
    monto: Decimal


class DevolucionResponse(BaseModel):
    model_config = _ORM
    id: UUID
    venta_id: UUID
    caja_turno_id: UUID
    usuario_id: UUID
    metodo_devolucion: MetodoDevolucion
    monto_devuelto: Decimal
    motivo: Optional[str] = None
    created_at: datetime
    lineas: List[DevolucionLineaResponse]


class LineaVentaResponse(BaseModel):
    model_config = _ORM
    id: UUID
    producto_id: UUID
    producto_unidad_id: Optional[UUID] = None
    cantidad: Decimal
    cantidad_en_unidad_base: Optional[Decimal] = None
    precio_unitario: Decimal
    descuento_linea: Decimal
    impuesto_tasa: Decimal
    promo_descuento: Decimal = Decimal("0")
    promo_etiqueta: Optional[str] = None
    cantidad_devuelta: Decimal = Decimal("0")
    subtotal: Decimal


class PagoResponse(BaseModel):
    model_config = _ORM
    id: UUID
    monto: Decimal
    metodo_pago: MetodoPago
    monto_recibido: Optional[Decimal] = None
    cambio: Decimal = Decimal("0")


class VentaResponse(EmbeddableModel):
    _embed_fields: ClassVar[tuple[str, ...]] = ("cliente", "usuario", "caja_turno")
    id: UUID
    sucursal_id: UUID
    caja_turno_id: UUID
    usuario_id: UUID
    cliente_id: Optional[UUID]
    estado: EstadoVenta
    descuento_total: Decimal
    total_promociones: Decimal
    total_devuelto: Decimal
    total: Decimal
    monto_pagado: Decimal
    efectivo_recibido: Decimal
    cambio: Decimal
    saldo_pendiente: Decimal
    created_at: datetime
    lineas: List[LineaVentaResponse]
    pagos: List[PagoResponse]
    # Embebidas (?include=cliente,usuario,caja_turno)
    cliente: Optional[ClienteEmbed] = None
    usuario: Optional[UsuarioEmbed] = None
    caja_turno: Optional[CajaTurnoEmbed] = None


class VentaListItem(EmbeddableModel):
    _embed_fields: ClassVar[tuple[str, ...]] = ("cliente", "usuario", "caja_turno")
    id: UUID
    sucursal_id: UUID
    caja_turno_id: UUID
    usuario_id: UUID
    cliente_id: Optional[UUID]
    estado: EstadoVenta
    total_promociones: Decimal
    total: Decimal
    saldo_pendiente: Decimal
    created_at: datetime
    cliente: Optional[ClienteEmbed] = None
    usuario: Optional[UsuarioEmbed] = None
    caja_turno: Optional[CajaTurnoEmbed] = None


# --------------------------------------------------------------------------- #
# Caja
# --------------------------------------------------------------------------- #
class AbrirCajaTurnoRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    saldo_inicial: Decimal = Field(ge=0)


class CerrarCajaTurnoRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    saldo_final_declarado: Decimal = Field(ge=0)


class CajaTurnoResponse(BaseModel):
    model_config = _ORM
    id: UUID
    sucursal_id: UUID
    usuario_id: UUID
    saldo_inicial: Decimal
    estado: str
    abierto_en: datetime
    cerrado_en: Optional[datetime]
    saldo_final_declarado: Optional[Decimal]
    diferencia: Optional[Decimal]


class ResumenTurnoResponse(BaseModel):
    turno: CajaTurnoResponse
    total_efectivo: Decimal
    total_devoluciones_efectivo: Decimal
    cantidad_ventas: int
    saldo_esperado: Decimal   # saldo_inicial + total_efectivo - total_devoluciones_efectivo
