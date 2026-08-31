from pydantic import BaseModel, Field
from typing import List, Optional
from uuid import UUID
from decimal import Decimal
from app.modules.ventas.domain.value_objects import MetodoPago, EstadoVenta

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

class LineaVentaResponse(BaseModel):
    id: UUID
    producto_id: UUID
    cantidad: Decimal
    precio_unitario: Decimal
    descuento_linea: Decimal
    impuesto_tasa: Decimal
    subtotal: Decimal

class PagoResponse(BaseModel):
    id: UUID
    monto: Decimal
    metodo_pago: MetodoPago

class VentaResponse(BaseModel):
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
    lineas: List[LineaVentaResponse]
    pagos: List[PagoResponse]
