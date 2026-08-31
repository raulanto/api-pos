from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict

_ORM = ConfigDict(from_attributes=True)


class CorteDeCajaResponse(BaseModel):
    model_config = _ORM
    caja_turno_id: UUID
    monto_inicial: Decimal
    total_efectivo: Decimal
    total_tarjeta: Decimal
    total_transferencia: Decimal
    total_credito: Decimal
    monto_final_esperado: Decimal
    nota: str


class VentasDiaResponse(BaseModel):
    model_config = _ORM
    dia: date
    numero_ventas: int
    total: Decimal


class ReporteVentasResponse(BaseModel):
    model_config = _ORM
    desde: datetime
    hasta: datetime
    sucursal_id: Optional[UUID]
    total_vendido: Decimal
    numero_ventas: int
    ticket_promedio: Decimal
    por_dia: List[VentasDiaResponse]


class MetodoPagoTotalResponse(BaseModel):
    model_config = _ORM
    metodo_pago: str
    total: Decimal


class VentasPorMetodoResponse(BaseModel):
    model_config = _ORM
    desde: datetime
    hasta: datetime
    sucursal_id: Optional[UUID]
    total_efectivo: Decimal
    total_tarjeta: Decimal
    total_transferencia: Decimal
    total_credito: Decimal
    total_general: Decimal
    detalle: List[MetodoPagoTotalResponse]


class VentaPorUsuarioResponse(BaseModel):
    model_config = _ORM
    usuario_id: UUID
    nombre: str
    numero_ventas: int
    total_vendido: Decimal


class ProductoRankingResponse(BaseModel):
    model_config = _ORM
    producto_id: UUID
    sku: str
    nombre: str
    cantidad_vendida: Decimal
    monto_total: Decimal


class CategoriaValorizadaResponse(BaseModel):
    model_config = _ORM
    categoria_id: UUID
    nombre: str
    valor: Decimal
    numero_productos: int


class InventarioValorizadoResponse(BaseModel):
    model_config = _ORM
    sucursal_id: Optional[UUID]
    categoria_id: Optional[UUID]
    valor_total: Decimal
    por_categoria: List[CategoriaValorizadaResponse]


class ClienteSaldoResponse(BaseModel):
    model_config = _ORM
    cliente_id: UUID
    nombre: str
    saldo_credito: Decimal
    limite_credito: Decimal



