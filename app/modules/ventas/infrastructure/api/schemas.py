from datetime import datetime
from decimal import Decimal
from typing import ClassVar, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.ventas.domain.value_objects import (
    MetodoPago, EstadoVenta, MetodoDevolucion, TipoMovimientoCaja,
)
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
    # Monedero: teléfono del comprador (opcional). Habilita el cashback y el
    # historial por teléfono; NO obliga a registrar un cliente. Obligatorio sólo
    # si algún pago es `metodo_pago="monedero"`.
    telefono: Optional[str] = Field(default=None, max_length=50)
    # Obligatorio si hay descuento manual (descuento_linea/descuento_total > 0).
    motivo_descuento: Optional[str] = Field(default=None, max_length=255)
    # Código de cupón que habilita una promo `requiere_cupon`.
    codigo_cupon: Optional[str] = Field(default=None, max_length=40)


class CotizarVentaRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    descuento_total: Decimal = Field(default=Decimal("0"), ge=0)
    lineas: List[LineaVentaRequest]
    # Hints opcionales para previsualizar promos condicionadas.
    metodos_pago: List[str] = []
    cliente_segmento: Optional[str] = None
    codigo_cupon: Optional[str] = Field(default=None, max_length=40)
    telefono: Optional[str] = Field(default=None, max_length=50)


class CuponValidarRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    codigo: str = Field(min_length=1, max_length=40)
    telefono: Optional[str] = Field(default=None, max_length=50)
    cliente_id: Optional[UUID] = None


class CuponValidacionResponse(BaseModel):
    promocion_id: UUID
    valido: bool = True


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
    monedero_a_generar: Decimal = Decimal("0")


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


class PromoAplicadaResponse(BaseModel):
    model_config = _ORM
    promo_id: Optional[UUID] = None
    etiqueta: Optional[str] = None
    monto: Decimal


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
    promos_aplicadas: List[PromoAplicadaResponse] = []
    cantidad_devuelta: Decimal = Decimal("0")
    cita_id: Optional[UUID] = None
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
    telefono: Optional[str] = None
    monedero_generado: Decimal = Decimal("0")
    monedero_usado: Decimal = Decimal("0")
    motivo_descuento: Optional[str] = None
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
    telefono: Optional[str] = None
    created_at: datetime
    cliente: Optional[ClienteEmbed] = None
    usuario: Optional[UsuarioEmbed] = None
    caja_turno: Optional[CajaTurnoEmbed] = None


# --------------------------------------------------------------------------- #
# Caja física (terminal)
# --------------------------------------------------------------------------- #
class CajaCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nombre: str = Field(min_length=1, max_length=60)


class CajaRenameRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nombre: str = Field(min_length=1, max_length=60)


class CajaResponse(BaseModel):
    model_config = _ORM
    id: UUID
    sucursal_id: UUID
    nombre: str
    activa: bool
    created_at: datetime


# --------------------------------------------------------------------------- #
# Caja: turnos, movimientos, arqueo
# --------------------------------------------------------------------------- #
class DenominacionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    valor: Decimal = Field(gt=0)      # valor de la pieza (ej. 500, 0.50)
    cantidad: int = Field(ge=0)


class AbrirCajaTurnoRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    caja_id: UUID
    saldo_inicial: Decimal = Field(ge=0)
    # Opcional: desglose por denominación; su suma debe cuadrar con saldo_inicial.
    denominaciones: List[DenominacionInput] = []


class CerrarCajaTurnoRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    saldo_final_declarado: Decimal = Field(ge=0)
    # Obligatoria si |diferencia| >= umbral (si no, el cierre da 400).
    nota_cierre: Optional[str] = Field(default=None, max_length=500)
    denominaciones: List[DenominacionInput] = []


class MovimientoCajaRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tipo: TipoMovimientoCaja
    monto: Decimal = Field(gt=0)
    # Obligatorio para `retiro` y `gasto`.
    motivo: Optional[str] = Field(default=None, max_length=255)


class MovimientoCajaResponse(BaseModel):
    model_config = _ORM
    id: UUID
    caja_turno_id: UUID
    tipo: TipoMovimientoCaja
    monto: Decimal
    motivo: Optional[str] = None
    usuario_id: UUID
    created_at: datetime


class ConciliarTurnoRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nota: Optional[str] = Field(default=None, max_length=500)


class CajaTurnoResponse(BaseModel):
    model_config = _ORM
    id: UUID
    sucursal_id: UUID
    caja_id: UUID
    usuario_id: UUID
    saldo_inicial: Decimal
    estado: str
    abierto_en: datetime
    cerrado_en: Optional[datetime]
    saldo_final_declarado: Optional[Decimal]
    diferencia: Optional[Decimal]
    nota_cierre: Optional[str] = None
    conciliado_por: Optional[UUID] = None
    conciliado_en: Optional[datetime] = None


class DenominacionResponse(BaseModel):
    model_config = _ORM
    valor: Decimal
    cantidad: int


class ResumenTurnoResponse(BaseModel):
    turno: CajaTurnoResponse
    total_efectivo: Decimal
    total_devoluciones_efectivo: Decimal
    cantidad_ventas: int
    total_ingresos: Decimal
    total_retiros: Decimal
    total_gastos: Decimal
    movimientos_neto: Decimal
    # saldo_esperado = saldo_inicial + total_efectivo - total_devoluciones_efectivo + movimientos_neto
    saldo_esperado: Decimal
    denominaciones_apertura: List[DenominacionResponse] = []
    denominaciones_cierre: List[DenominacionResponse] = []


class TurnoListItem(BaseModel):
    model_config = _ORM
    id: UUID
    sucursal_id: UUID
    caja_id: UUID
    usuario_id: UUID
    estado: str
    saldo_inicial: Decimal
    saldo_final_declarado: Optional[Decimal] = None
    diferencia: Optional[Decimal] = None
    abierto_en: datetime
    cerrado_en: Optional[datetime] = None


class EfectivoSucursalResponse(BaseModel):
    sucursal_id: UUID
    efectivo_esperado: Decimal
