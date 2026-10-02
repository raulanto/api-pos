from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
import uuid

from app.shared.infrastructure.orm_base import Base, TimestampMixin


class NotificacionORM(Base, TimestampMixin):
    __tablename__ = "notificacion"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    usuario_id = Column(PGUUID(as_uuid=True), ForeignKey("usuario.id"), nullable=False, index=True)
    sucursal_id = Column(PGUUID(as_uuid=True), ForeignKey("sucursal.id"), nullable=True, index=True)
    modulo = Column(String(50), nullable=False, index=True)
    tipo = Column(String(50), nullable=False)
    titulo = Column(String(200), nullable=False)
    mensaje = Column(String, nullable=False)
    leida = Column(Boolean, nullable=False, default=False, index=True)
    fecha_leida = Column(DateTime(timezone=True), nullable=True)
    entidad = Column(String(100), nullable=True)
    entidad_id = Column(String(100), nullable=True)
    datos = Column(JSONB, nullable=False, default=dict)

    __table_args__ = (
        Index("idx_notificacion_usuario_leida", "usuario_id", "leida"),
        Index("idx_notificacion_created_at", "created_at"),
    )
