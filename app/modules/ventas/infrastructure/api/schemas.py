from datetime import datetime
from decimal import Decimal
from typing import ClassVar, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.ventas.domain.value_objects import MetodoPago, EstadoVenta
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


class PagoRequest(BaseModel):
    monto: Decimal = Field(gt=0)
    metodo_pago: MetodoPago


class CrearVentaRequest(BaseModel):
    caja_turno_id: UUID
    cliente_id: Optional[UUID] = None
    descuento_total: Decimal = Field(default=Decimal("0"), ge=0)
    lineas: List[LineaVentaRequest]
    pagos: List[PagoRequest]


class AnularVentaRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    motivo: Optional[str] = Field(default=None, max_length=255)


class LineaVentaResponse(BaseModel):
    model_config = _ORM
    id: UUID
    producto_id: UUID
    cantidad: Decimal
    precio_unitario: Decimal
    descuento_linea: Decimal
    impuesto_tasa: Decimal
    subtotal: Decimal


class PagoResponse(BaseModel):
    model_config = _ORM
    id: UUID
    monto: Decimal
    metodo_pago: MetodoPago


class VentaResponse(EmbeddableModel):
    _embed_fields: ClassVar[tuple[str, ...]] = ("cliente", "usuario", "caja_turno")
    id: UUID
    sucursal_id: UUID
    caja_turno_id: UUID
    usuario_id: UUID
    cliente_id: Optional[UUID]
    estado: EstadoVenta
    descuento_total: Decimal
    total: Decimal
    monto_pagado: Decimal
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
    cantidad_ventas: int
    saldo_esperado: Decimal
