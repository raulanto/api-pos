import uuid
from sqlalchemy import Column, String, ForeignKey, Numeric, DateTime
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship
from app.shared.infrastructure.orm_base import Base, TimestampMixin

class CajaTurnoORM(Base):
    __tablename__ = "caja_turno"
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sucursal_id = Column(PGUUID(as_uuid=True), ForeignKey("sucursal.id"), nullable=False)
    usuario_id = Column(PGUUID(as_uuid=True), ForeignKey("usuario.id"), nullable=False)
    saldo_inicial = Column(Numeric(12, 2), nullable=False)
    estado = Column(String(20), nullable=False, default="abierto")
    abierto_en = Column(DateTime(timezone=True), nullable=False)
    cerrado_en = Column(DateTime(timezone=True), nullable=True)
    saldo_final_declarado = Column(Numeric(12, 2), nullable=True)
    diferencia = Column(Numeric(12, 2), nullable=True)

class VentaORM(Base, TimestampMixin):
    __tablename__ = "venta"
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sucursal_id = Column(PGUUID(as_uuid=True), ForeignKey("sucursal.id"), nullable=False)
    caja_turno_id = Column(PGUUID(as_uuid=True), ForeignKey("caja_turno.id"), nullable=False)
    usuario_id = Column(PGUUID(as_uuid=True), ForeignKey("usuario.id"), nullable=False)
    cliente_id = Column(PGUUID(as_uuid=True), ForeignKey("cliente.id"), nullable=True)
    estado = Column(String(30), nullable=False)
    descuento_total = Column(Numeric(12, 2), nullable=False, default=0)
    idempotency_key = Column(String(80), nullable=True, unique=True)

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
    cantidad = Column(Numeric(12, 2), nullable=False)
    precio_unitario = Column(Numeric(12, 2), nullable=False)
    descuento_linea = Column(Numeric(12, 2), nullable=False, default=0)
    impuesto_tasa = Column(Numeric(5, 2), nullable=False, default=0)

class PagoORM(Base, TimestampMixin):
    __tablename__ = "pago"
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    venta_id = Column(PGUUID(as_uuid=True), ForeignKey("venta.id"), nullable=False)
    monto = Column(Numeric(12, 2), nullable=False)
    metodo_pago = Column(String(50), nullable=False)
