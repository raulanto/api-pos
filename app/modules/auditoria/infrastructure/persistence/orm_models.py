import uuid
from sqlalchemy import Column, String, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from sqlalchemy.orm import relationship
from datetime import datetime
from app.shared.infrastructure.orm_base import Base


"""
    Tabla: log_auditoria
    Descripcion: Tabla que almacena los logs de auditoria.
    Columnas:
    - id: ID del log.
    - usuario_id: ID del usuario.
    - modulo: Modulo.
    - accion: Accion.
    - entidad: Entidad.
    - entidad_id: ID de la entidad.
    - detalle: Detalle.
    - ip_address: Direccion IP.
    - fecha: Fecha.
    Relaciones:
    - usuario_id: FK a usuario.id
"""
class LogAuditoriaORM(Base):
    __tablename__ = "log_auditoria"
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    usuario_id = Column(PGUUID(as_uuid=True), ForeignKey("usuario.id"), nullable=False)
    modulo = Column(String(50), nullable=False)
    accion = Column(String(100), nullable=False)
    entidad = Column(String(100), nullable=False)
    entidad_id = Column(String(100), nullable=False)
    detalle = Column(JSONB, nullable=True)
    ip_address = Column(String(45), nullable=True)
    fecha = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    # Solo lectura, para `?include=usuario`.
    usuario = relationship("UsuarioORM", viewonly=True, lazy="raise")
