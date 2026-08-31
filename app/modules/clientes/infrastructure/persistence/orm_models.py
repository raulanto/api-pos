import uuid
from sqlalchemy import Column, String, Boolean, ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from app.shared.infrastructure.orm_base import Base, TimestampMixin, SoftDeleteMixin

class ClienteORM(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "cliente"
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sucursal_id = Column(PGUUID(as_uuid=True), ForeignKey("sucursal.id"), nullable=False)
    nombre = Column(String(150), nullable=False)
    email = Column(String(150), nullable=True)
    telefono = Column(String(50), nullable=True)
    rfc_identificacion = Column(String(50), nullable=True)
    limite_credito = Column(Numeric(12, 2), default=0, nullable=False)
    saldo_credito = Column(Numeric(12, 2), default=0, nullable=False)
