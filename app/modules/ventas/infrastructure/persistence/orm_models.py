import uuid
from sqlalchemy import (
    Column, String, Text, Boolean, Integer, ForeignKey, Numeric, DateTime,
    CheckConstraint, Index, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.shared.infrastructure.orm_base import Base, TimestampMixin


class CajaORM(Base, TimestampMixin):
    """Caja física / terminal de una sucursal."""
    __tablename__ = "caja"
    __table_args__ = (
        # Nombre único entre cajas activas de la sucursal (case-insensitive lo
        # valida el repo con func.lower, igual que producto/lote).
        Index(
            "uq_caja_nombre_activa", "sucursal_id", "nombre",
            unique=True, postgresql_where=Column("activa"),
        ),
    )
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sucursal_id = Column(PGUUID(as_uuid=True), ForeignKey("sucursal.id"), nullable=False)
    nombre = Column(String(60), nullable=False)
    activa = Column(Boolean, nullable=False, default=True)


class CajaTurnoORM(Base):
    __tablename__ = "caja_turno"
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sucursal_id = Column(PGUUID(as_uuid=True), ForeignKey("sucursal.id"), nullable=False)
    caja_id = Column(PGUUID(as_uuid=True), ForeignKey("caja.id"), nullable=False)
    usuario_id = Column(PGUUID(as_uuid=True), ForeignKey("usuario.id"), nullable=False)
    saldo_inicial = Column(Numeric(12, 2), nullable=False)
    estado = Column(String(30), nullable=False, default="abierto")
    abierto_en = Column(DateTime(timezone=True), nullable=False)
    cerrado_en = Column(DateTime(timezone=True), nullable=True)
    saldo_final_declarado = Column(Numeric(12, 2), nullable=True)
    diferencia = Column(Numeric(12, 2), nullable=True)
    # Justificación de la diferencia (obligatoria si |diferencia| >= umbral).
    nota_cierre = Column(Text, nullable=True)
    # Conciliación de un turno cerrado con diferencia (gerente/admin).
    conciliado_por = Column(PGUUID(as_uuid=True), ForeignKey("usuario.id"), nullable=True)
    conciliado_en = Column(DateTime(timezone=True), nullable=True)


class CajaMovimientoORM(Base):
    """Retiro / ingreso / gasto de efectivo durante un turno. Append-only."""
    __tablename__ = "caja_movimiento"
    __table_args__ = (
        CheckConstraint(
            "tipo IN ('retiro', 'ingreso', 'gasto')", name="ck_caja_movimiento_tipo",
        ),
        CheckConstraint("monto > 0", name="ck_caja_movimiento_monto_pos"),
        Index("ix_caja_movimiento_turno", "caja_turno_id"),
    )
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    caja_turno_id = Column(
        PGUUID(as_uuid=True), ForeignKey("caja_turno.id"), nullable=False,
    )
    tipo = Column(String(20), nullable=False)
    monto = Column(Numeric(12, 2), nullable=False)
    motivo = Column(Text, nullable=True)
    usuario_id = Column(PGUUID(as_uuid=True), ForeignKey("usuario.id"), nullable=False)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )


class CajaDenominacionORM(Base):
    """Desglose por denominación (valor de la pieza × cantidad) en apertura/cierre."""
    __tablename__ = "caja_denominacion"
    __table_args__ = (
        CheckConstraint(
            "momento IN ('apertura', 'cierre')", name="ck_caja_denominacion_momento",
        ),
        CheckConstraint("cantidad >= 0", name="ck_caja_denominacion_cantidad"),
        UniqueConstraint(
            "caja_turno_id", "momento", "valor", name="uq_caja_denominacion",
        ),
        Index("ix_caja_denominacion_turno", "caja_turno_id"),
    )
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    caja_turno_id = Column(
        PGUUID(as_uuid=True), ForeignKey("caja_turno.id"), nullable=False,
    )
    momento = Column(String(10), nullable=False)
    valor = Column(Numeric(12, 2), nullable=False)
    cantidad = Column(Integer, nullable=False)

class VentaORM(Base, TimestampMixin):
    __tablename__ = "venta"
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sucursal_id = Column(PGUUID(as_uuid=True), ForeignKey("sucursal.id"), nullable=False)
    caja_turno_id = Column(PGUUID(as_uuid=True), ForeignKey("caja_turno.id"), nullable=False)
    usuario_id = Column(PGUUID(as_uuid=True), ForeignKey("usuario.id"), nullable=False)
    cliente_id = Column(PGUUID(as_uuid=True), ForeignKey("cliente.id"), nullable=True)
    estado = Column(String(30), nullable=False)
    descuento_total = Column(Numeric(12, 2), nullable=False, default=0)
    # Motivo del descuento manual (`descuento_linea`/`descuento_total`); obligatorio
    # cuando hay descuento manual, se congela acá.
    motivo_descuento = Column(Text, nullable=True)
    idempotency_key = Column(String(80), nullable=True, unique=True)
    # Monedero: teléfono opcional del comprador (historial + cashback) y saldo de
    # monedero que la venta generó (congelado).
    telefono = Column(String(50), nullable=True, index=True)
    monedero_generado = Column(Numeric(12, 2), nullable=False, default=0)

    lineas = relationship("DetalleVentaORM", backref="venta", cascade="all, delete-orphan")
    pagos = relationship("PagoORM", backref="venta", cascade="all, delete-orphan")

    # Relaciones de solo lectura para `?include=` (no participan en escrituras).
    cliente = relationship("ClienteORM", viewonly=True, lazy="raise")
    usuario = relationship("UsuarioORM", viewonly=True, lazy="raise")
    caja_turno = relationship("CajaTurnoORM", viewonly=True, lazy="raise")

class DetalleVentaORM(Base):
    __tablename__ = "detalle_venta"
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    venta_id = Column(PGUUID(as_uuid=True), ForeignKey("venta.id"), nullable=False)
    producto_id = Column(PGUUID(as_uuid=True), ForeignKey("producto.id"), nullable=False)
    cantidad = Column(Numeric(14, 4), nullable=False)
    precio_unitario = Column(Numeric(12, 2), nullable=False)
    descuento_linea = Column(Numeric(12, 2), nullable=False, default=0)
    impuesto_tasa = Column(Numeric(5, 2), nullable=False, default=0)
    producto_unidad_id = Column(
        PGUUID(as_uuid=True), ForeignKey("producto_unidad.id"), nullable=True
    )
    # Cantidad equivalente en la unidad base del producto (cantidad * factor de
    # la presentación). Se persiste para no recalcularla en anulaciones/reportes.
    cantidad_en_unidad_base = Column(Numeric(14, 4), nullable=True)
    # Promoción aplicada (motor de `promociones`). `promo_descuento` resta en el
    # subtotal, aparte del `descuento_linea` manual; `promo_etiqueta` es el
    # nombre de la promo congelado al momento de la venta.
    promo_id = Column(PGUUID(as_uuid=True), ForeignKey("promocion.id"), nullable=True)
    promo_descuento = Column(Numeric(12, 2), nullable=False, default=0)
    promo_etiqueta = Column(String(120), nullable=True)
    # Cantidad de esta línea ya devuelta (acumulado). Sube con cada devolución.
    cantidad_devuelta = Column(Numeric(14, 4), nullable=False, default=0)

    promos = relationship(
        "DetalleVentaPromoORM", backref="detalle", cascade="all, delete-orphan",
        lazy="selectin",
    )


class DescuentoManualLimiteORM(Base):
    """Tope de % de descuento manual por rol. `pct_max` NULL (o sin fila) = sin
    tope. El permiso `ventas.descuento_manual` es el gate; esto sólo restringe."""
    __tablename__ = "descuento_manual_limite"
    rol_id = Column(PGUUID(as_uuid=True), ForeignKey("rol.id"), primary_key=True)
    pct_max = Column(Numeric(5, 2), nullable=True)


class DetalleVentaPromoORM(Base):
    """Desglose congelado de las promociones aplicadas a una línea (append-only).
    `detalle_venta.promo_descuento` es la Σ de estos montos."""
    __tablename__ = "detalle_venta_promo"
    __table_args__ = (Index("ix_detalle_venta_promo_detalle", "detalle_venta_id"),)
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    detalle_venta_id = Column(
        PGUUID(as_uuid=True), ForeignKey("detalle_venta.id", ondelete="CASCADE"),
        nullable=False,
    )
    promo_id = Column(PGUUID(as_uuid=True), ForeignKey("promocion.id"), nullable=True)
    promo_etiqueta = Column(String(120), nullable=True)
    monto = Column(Numeric(12, 2), nullable=False)


class PagoORM(Base, TimestampMixin):
    __tablename__ = "pago"
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    venta_id = Column(PGUUID(as_uuid=True), ForeignKey("venta.id"), nullable=False)
    monto = Column(Numeric(12, 2), nullable=False)
    metodo_pago = Column(String(50), nullable=False)
    # Sólo efectivo: con cuánto pagó el cliente (para calcular el cambio en el ticket).
    monto_recibido = Column(Numeric(12, 2), nullable=True)


class DevolucionORM(Base, TimestampMixin):
    __tablename__ = "devolucion"
    __table_args__ = (
        CheckConstraint(
            "metodo_devolucion IN ('efectivo', 'tarjeta', 'credito', 'monedero')",
            name="ck_devolucion_metodo",
        ),
    )
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    venta_id = Column(PGUUID(as_uuid=True), ForeignKey("venta.id"), nullable=False, index=True)
    caja_turno_id = Column(PGUUID(as_uuid=True), ForeignKey("caja_turno.id"), nullable=False)
    usuario_id = Column(PGUUID(as_uuid=True), ForeignKey("usuario.id"), nullable=False)
    motivo = Column(Text, nullable=True)
    monto_devuelto = Column(Numeric(12, 2), nullable=False)
    metodo_devolucion = Column(String(20), nullable=False)
    idempotency_key = Column(String(80), nullable=True, unique=True)

    lineas = relationship(
        "DevolucionLineaORM", backref="devolucion", cascade="all, delete-orphan",
    )


class DevolucionLineaORM(Base):
    __tablename__ = "devolucion_linea"
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    devolucion_id = Column(
        PGUUID(as_uuid=True), ForeignKey("devolucion.id", ondelete="CASCADE"), nullable=False,
    )
    detalle_venta_id = Column(
        PGUUID(as_uuid=True), ForeignKey("detalle_venta.id"), nullable=False,
    )
    cantidad = Column(Numeric(14, 4), nullable=False)
    monto = Column(Numeric(12, 2), nullable=False)
