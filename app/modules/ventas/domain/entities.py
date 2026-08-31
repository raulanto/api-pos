from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4
from app.modules.ventas.domain.value_objects import EstadoVenta, MetodoPago
from app.modules.ventas.domain.exceptions import VentaSinLineas, VentaYaCancelada

@dataclass
class DetalleVenta:
    id: UUID
    venta_id: UUID
    producto_id: UUID
    cantidad: Decimal
    precio_unitario: Decimal
    descuento_linea: Decimal = Decimal("0")
    impuesto_tasa: Decimal = Decimal("0")

    @staticmethod
    def crear(producto_id: UUID, cantidad: Decimal, precio_unitario: Decimal,
              descuento_linea: Decimal = Decimal("0"), impuesto_tasa: Decimal = Decimal("0")) -> "DetalleVenta":
        return DetalleVenta(
            id=uuid4(), venta_id=uuid4(), # venta_id is a placeholder until attached to Venta
            producto_id=producto_id, cantidad=cantidad, precio_unitario=precio_unitario,
            descuento_linea=descuento_linea, impuesto_tasa=impuesto_tasa
        )

    @property
    def subtotal(self) -> Decimal:
        return (self.cantidad * self.precio_unitario) - self.descuento_linea

@dataclass
class Pago:
    id: UUID
    venta_id: UUID
    monto: Decimal
    metodo_pago: MetodoPago
    created_at: datetime = field(default_factory=datetime.utcnow)

    @staticmethod
    def crear(monto: Decimal, metodo_pago: MetodoPago) -> "Pago":
        return Pago(id=uuid4(), venta_id=uuid4(), monto=monto, metodo_pago=metodo_pago)

@dataclass
class Venta:
    id: UUID
    sucursal_id: UUID
    caja_turno_id: UUID
    usuario_id: UUID
    cliente_id: UUID | None
    estado: EstadoVenta
    descuento_total: Decimal = Decimal("0")
    lineas: list[DetalleVenta] = field(default_factory=list)
    pagos: list[Pago] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)

    @staticmethod
    def crear(sucursal_id: UUID, caja_turno_id: UUID, usuario_id: UUID,
              cliente_id: UUID | None, lineas: list[DetalleVenta], pagos: list[Pago],
              descuento_total: Decimal = Decimal("0")) -> "Venta":
        if not lineas:
            raise VentaSinLineas("Una venta debe tener al menos una línea")
        
        venta_id = uuid4()
        for linea in lineas:
            linea.venta_id = venta_id
        for pago in pagos:
            pago.venta_id = venta_id

        return Venta(
            id=venta_id, sucursal_id=sucursal_id, caja_turno_id=caja_turno_id,
            usuario_id=usuario_id, cliente_id=cliente_id,
            estado=EstadoVenta.PENDIENTE_PAGO, lineas=lineas, pagos=pagos,
            descuento_total=descuento_total
        )

    @property
    def total(self) -> Decimal:
        subtotal = sum((linea.subtotal for linea in self.lineas), Decimal("0"))
        return subtotal - self.descuento_total

    @property
    def monto_pagado(self) -> Decimal:
        return sum((p.monto for p in self.pagos), Decimal("0"))

    @property
    def saldo_pendiente(self) -> Decimal:
        return self.total - self.monto_pagado

    def actualizar_estado_por_pago(self) -> None:
        if self.saldo_pendiente <= Decimal("0"):
            self.estado = EstadoVenta.PAGADA

    def cancelar(self) -> None:
        if self.estado == EstadoVenta.CANCELADA:
            raise VentaYaCancelada(f"La venta {self.id} ya está cancelada")
        self.estado = EstadoVenta.CANCELADA

@dataclass
class CajaTurno:
    id: UUID
    sucursal_id: UUID
    usuario_id: UUID
    saldo_inicial: Decimal
    estado: str # "abierto" or "cerrado"
    abierto_en: datetime
    cerrado_en: datetime | None = None
