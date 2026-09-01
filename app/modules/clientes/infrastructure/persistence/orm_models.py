import uuid
from sqlalchemy import Column, String, ForeignKey, Numeric, Index
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
