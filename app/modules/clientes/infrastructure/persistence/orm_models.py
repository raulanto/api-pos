import uuid
from sqlalchemy import (
    Column, String, Text, ForeignKey, Numeric, Index, CheckConstraint, DateTime,
)
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship
from app.shared.infrastructure.orm_base import Base, TimestampMixin, SoftDeleteMixin

class ClienteORM(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "cliente"
    # Email único sólo entre clientes activos: un cliente dado de baja libera su email.
    __table_args__ = (
        Index(
            "uq_cliente_email_activo", "email",
            unique=True, postgresql_where=Column("activo"),
        ),
    )
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sucursal_id = Column(PGUUID(as_uuid=True), ForeignKey("sucursal.id"), nullable=False)
    nombre = Column(String(150), nullable=False)
    email = Column(String(150), nullable=True)
    telefono = Column(String(50), nullable=True)
    rfc_identificacion = Column(String(50), nullable=True)
    limite_credito = Column(Numeric(12, 2), default=0, nullable=False)
    saldo_credito = Column(Numeric(12, 2), default=0, nullable=False)

    # Solo lectura, para `?include=sucursal`.
    sucursal = relationship("SucursalORM", viewonly=True, lazy="raise")


class MonederoCuentaORM(Base, TimestampMixin, SoftDeleteMixin):
    """Saldo de monedero por teléfono. Sin FK a `cliente`: es independiente."""
    __tablename__ = "monedero_cuenta"
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    telefono = Column(String(50), nullable=False, unique=True)
    saldo = Column(Numeric(12, 2), nullable=False, default=0)


class MonederoMovimientoORM(Base):
    """Ledger del monedero = historial. `monto` siempre positivo; el efecto en el
    saldo lo da `tipo`."""
    __tablename__ = "monedero_movimiento"
    __table_args__ = (
        CheckConstraint(
            "tipo IN ('acumulacion', 'consumo', 'reverso_acumulacion', "
            "'reverso_consumo', 'ajuste')",
            name="ck_monedero_movimiento_tipo",
        ),
        Index("ix_monedero_movimiento_cuenta", "cuenta_id"),
        Index("ix_monedero_movimiento_venta", "venta_id"),
    )
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cuenta_id = Column(
        PGUUID(as_uuid=True), ForeignKey("monedero_cuenta.id"), nullable=False,
    )
    tipo = Column(String(30), nullable=False)
    monto = Column(Numeric(12, 2), nullable=False)
    saldo_resultante = Column(Numeric(12, 2), nullable=False)
    venta_id = Column(PGUUID(as_uuid=True), ForeignKey("venta.id"), nullable=True)
    usuario_id = Column(PGUUID(as_uuid=True), ForeignKey("usuario.id"), nullable=True)
    motivo = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )
