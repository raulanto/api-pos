from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4
from app.modules.ventas.domain.value_objects import EstadoVenta, MetodoPago, MetodoDevolucion
from app.modules.ventas.domain.exceptions import (
    VentaSinLineas, VentaYaCancelada, TurnoYaCerrado, DevolucionInvalida,
)

@dataclass
class DetalleVenta:
    id: UUID
    venta_id: UUID
    producto_id: UUID
    cantidad: Decimal
    precio_unitario: Decimal
    descuento_linea: Decimal = Decimal("0")
    impuesto_tasa: Decimal = Decimal("0")
    # Presentación vendida (producto_unidad). None = unidad base (factor 1).
    producto_unidad_id: UUID | None = None
    # `cantidad` convertida a la unidad base del producto (cantidad * factor).
    # La fija el caso de uso vía InventarioPort.convertir_a_base antes de guardar.
    cantidad_en_unidad_base: Decimal | None = None
    # Promoción aplicada por el motor de `promociones` (2x1, %, precio fijo). El
    # backend la fuerza y la congela acá; `promo_descuento` resta en el subtotal.
    promo_id: UUID | None = None
    promo_etiqueta: str | None = None
    promo_descuento: Decimal = Decimal("0")
    # Cantidad de esta línea ya devuelta (acumulado de todas las devoluciones).
    cantidad_devuelta: Decimal = Decimal("0")

    @staticmethod
    def crear(producto_id: UUID, cantidad: Decimal, precio_unitario: Decimal,
              descuento_linea: Decimal = Decimal("0"), impuesto_tasa: Decimal = Decimal("0"),
              producto_unidad_id: UUID | None = None,
              cantidad_en_unidad_base: Decimal | None = None,
              promo_id: UUID | None = None, promo_etiqueta: str | None = None,
              promo_descuento: Decimal = Decimal("0")) -> "DetalleVenta":
        return DetalleVenta(
            id=uuid4(), venta_id=uuid4(), # venta_id is a placeholder until attached to Venta
            producto_id=producto_id, cantidad=cantidad, precio_unitario=precio_unitario,
            descuento_linea=descuento_linea, impuesto_tasa=impuesto_tasa,
            producto_unidad_id=producto_unidad_id,
            cantidad_en_unidad_base=cantidad_en_unidad_base,
            promo_id=promo_id, promo_etiqueta=promo_etiqueta,
            promo_descuento=promo_descuento,
        )

    @property
    def subtotal(self) -> Decimal:
        return (self.cantidad * self.precio_unitario) - self.descuento_linea - self.promo_descuento

    @property
    def cantidad_devolvible(self) -> Decimal:
        return self.cantidad - self.cantidad_devuelta

    @property
    def precio_neto_unitario(self) -> Decimal:
        """`subtotal` prorrateado por unidad (incluye descuento_linea y promo)."""
        if not self.cantidad:
            return Decimal("0")
        return self.subtotal / self.cantidad


@dataclass
class DevolucionLinea:
    id: UUID
    devolucion_id: UUID
    detalle_venta_id: UUID
    cantidad: Decimal
    monto: Decimal

    @staticmethod
    def crear(detalle_venta_id: UUID, cantidad: Decimal, monto: Decimal) -> "DevolucionLinea":
        if cantidad <= 0:
            raise DevolucionInvalida("La cantidad a devolver debe ser mayor a 0.")
        if monto < 0:
            raise DevolucionInvalida("El monto a devolver no puede ser negativo.")
        return DevolucionLinea(
            id=uuid4(), devolucion_id=uuid4(),
            detalle_venta_id=detalle_venta_id, cantidad=cantidad, monto=monto,
        )


@dataclass
class Devolucion:
    id: UUID
    venta_id: UUID
    caja_turno_id: UUID
    usuario_id: UUID
    metodo_devolucion: MetodoDevolucion
    monto_devuelto: Decimal
    motivo: str | None = None
    idempotency_key: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    lineas: list[DevolucionLinea] = field(default_factory=list)

    @staticmethod
    def crear(venta_id: UUID, caja_turno_id: UUID, usuario_id: UUID,
              metodo_devolucion: MetodoDevolucion, lineas: list[DevolucionLinea],
              motivo: str | None = None, idempotency_key: str | None = None) -> "Devolucion":
        if not lineas:
            raise DevolucionInvalida("Una devolución necesita al menos una línea.")
        dev_id = uuid4()
        for l in lineas:
            l.devolucion_id = dev_id
        return Devolucion(
            id=dev_id, venta_id=venta_id, caja_turno_id=caja_turno_id,
            usuario_id=usuario_id, metodo_devolucion=metodo_devolucion,
            monto_devuelto=sum((l.monto for l in lineas), Decimal("0")),
            motivo=motivo, idempotency_key=idempotency_key, lineas=lineas,
        )


@dataclass
class Pago:
    id: UUID
    venta_id: UUID
    monto: Decimal              # lo que se aplica a la venta
    metodo_pago: MetodoPago
    # Sólo efectivo: con cuánto pagó el cliente. `cambio` = monto_recibido - monto.
    monto_recibido: Decimal | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)

    @staticmethod
    def crear(monto: Decimal, metodo_pago: MetodoPago,
              monto_recibido: Decimal | None = None) -> "Pago":
        if monto_recibido is not None and monto_recibido < monto:
            raise ValueError(
                f"El monto recibido ({monto_recibido}) no puede ser menor al del pago ({monto})."
            )
        return Pago(
            id=uuid4(), venta_id=uuid4(), monto=monto, metodo_pago=metodo_pago,
            monto_recibido=monto_recibido,
        )

    @property
    def cambio(self) -> Decimal:
        if self.monto_recibido is None:
            return Decimal("0")
        return self.monto_recibido - self.monto

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

    idempotency_key: str | None = None

    # Relaciones embebidas opcionales (`?include=`); las puebla el mapper.
    cliente: object | None = field(default=None, compare=False, repr=False)
    usuario: object | None = field(default=None, compare=False, repr=False)
    caja_turno: object | None = field(default=None, compare=False, repr=False)

    @staticmethod
    def crear(sucursal_id: UUID, caja_turno_id: UUID, usuario_id: UUID,
              cliente_id: UUID | None, lineas: list[DetalleVenta], pagos: list[Pago],
              descuento_total: Decimal = Decimal("0"),
              idempotency_key: str | None = None) -> "Venta":
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
            descuento_total=descuento_total, idempotency_key=idempotency_key
        )

    @property
    def total(self) -> Decimal:
        subtotal = sum((linea.subtotal for linea in self.lineas), Decimal("0"))
        return subtotal - self.descuento_total

    @property
    def total_promociones(self) -> Decimal:
        """Suma de lo que descontaron las promociones (2x1, %, precio fijo) en
        todas las líneas. Informativo: ya está restado en `total`."""
        return sum((linea.promo_descuento for linea in self.lineas), Decimal("0"))

    @property
    def total_devuelto(self) -> Decimal:
        """Monto acumulado devuelto (prorrateado por cantidad de cada línea)."""
        return sum(
            (linea.precio_neto_unitario * linea.cantidad_devuelta for linea in self.lineas),
            Decimal("0"),
        )

    def recalcular_estado_devolucion(self) -> None:
        """Tras aplicar cantidades devueltas: DEVUELTA_TOTAL si no queda nada por
        devolver en ninguna línea, si no DEVUELTA_PARCIAL. No toca ventas
        canceladas."""
        if self.estado == EstadoVenta.CANCELADA:
            return
        if all(l.cantidad_devuelta >= l.cantidad for l in self.lineas):
            self.estado = EstadoVenta.DEVUELTA_TOTAL
        elif any(l.cantidad_devuelta > 0 for l in self.lineas):
            self.estado = EstadoVenta.DEVUELTA_PARCIAL

    @property
    def monto_pagado(self) -> Decimal:
        return sum((p.monto for p in self.pagos), Decimal("0"))

    @property
    def efectivo_recibido(self) -> Decimal:
        """Total en efectivo que entregó el cliente (donde el POS lo declaró)."""
        return sum(
            (p.monto_recibido for p in self.pagos if p.monto_recibido is not None),
            Decimal("0"),
        )

    @property
    def cambio(self) -> Decimal:
        return sum((p.cambio for p in self.pagos), Decimal("0"))

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

ESTADO_TURNO_ABIERTO = "abierto"
ESTADO_TURNO_CERRADO = "cerrado"


@dataclass
class CajaTurno:
    id: UUID
    sucursal_id: UUID
    usuario_id: UUID
    saldo_inicial: Decimal
    estado: str  # "abierto" | "cerrado"
    abierto_en: datetime
    cerrado_en: datetime | None = None
    saldo_final_declarado: Decimal | None = None
    # diferencia = saldo_final_declarado - saldo_esperado
    # (positivo => sobrante, negativo => faltante)
    diferencia: Decimal | None = None

    @staticmethod
    def abrir(sucursal_id: UUID, usuario_id: UUID, saldo_inicial: Decimal) -> "CajaTurno":
        if saldo_inicial < 0:
            raise ValueError("El saldo inicial no puede ser negativo")
        return CajaTurno(
            id=uuid4(),
            sucursal_id=sucursal_id,
            usuario_id=usuario_id,
            saldo_inicial=saldo_inicial,
            estado=ESTADO_TURNO_ABIERTO,
            abierto_en=datetime.utcnow(),
        )

    @property
    def esta_abierto(self) -> bool:
        return self.estado == ESTADO_TURNO_ABIERTO

    def cerrar(self, saldo_final_declarado: Decimal, saldo_esperado: Decimal) -> None:
        if not self.esta_abierto:
            raise TurnoYaCerrado(f"El turno {self.id} ya está cerrado")
        self.saldo_final_declarado = saldo_final_declarado
        self.diferencia = saldo_final_declarado - saldo_esperado
        self.estado = ESTADO_TURNO_CERRADO
        self.cerrado_en = datetime.utcnow()
