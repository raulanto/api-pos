import uuid
from sqlalchemy import (
    Column, String, Text, Boolean, Integer, Numeric, DateTime, Date, Time,
    SmallInteger, ForeignKey, CheckConstraint, Index, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.shared.infrastructure.orm_base import Base, TimestampMixin


class RecursoORM(Base, TimestampMixin):
    __tablename__ = "recurso"
    __table_args__ = (
        Index(
            "uq_recurso_nombre_activo", "sucursal_id", "nombre",
            unique=True, postgresql_where=Column("activo"),
        ),
    )
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sucursal_id = Column(PGUUID(as_uuid=True), ForeignKey("sucursal.id"), nullable=False)
    nombre = Column(String(80), nullable=False)
    tipo = Column(String(30), nullable=True)
    activo = Column(Boolean, default=True, nullable=False)


class EmpleadoServicioORM(Base):
    __tablename__ = "empleado_servicio"
    __table_args__ = (
        UniqueConstraint("empleado_id", "servicio_id", name="uq_empleado_servicio"),
    )
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    empleado_id = Column(PGUUID(as_uuid=True), ForeignKey("usuario.id"), nullable=False)
    servicio_id = Column(PGUUID(as_uuid=True), ForeignKey("producto.id"), nullable=False)
    activo = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class DisponibilidadHorarioORM(Base):
    __tablename__ = "disponibilidad_horario"
    __table_args__ = (Index("ix_disponibilidad_horario_empleado", "empleado_id"),)
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    empleado_id = Column(PGUUID(as_uuid=True), ForeignKey("usuario.id"), nullable=False)
    sucursal_id = Column(PGUUID(as_uuid=True), ForeignKey("sucursal.id"), nullable=False)
    dia_semana = Column(SmallInteger, nullable=False)   # 0=lunes .. 6=domingo
    hora_inicio = Column(Time, nullable=False)
    hora_fin = Column(Time, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class DisponibilidadExcepcionORM(Base):
    __tablename__ = "disponibilidad_excepcion"
    __table_args__ = (
        CheckConstraint(
            "tipo IN ('bloqueo', 'horario_especial')", name="ck_disponibilidad_excepcion_tipo",
        ),
        Index("ix_disponibilidad_excepcion_empleado_fecha", "empleado_id", "fecha"),
    )
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    empleado_id = Column(PGUUID(as_uuid=True), ForeignKey("usuario.id"), nullable=False)
    fecha = Column(Date, nullable=False)
    tipo = Column(String(20), nullable=False)
    hora_inicio = Column(Time, nullable=True)
    hora_fin = Column(Time, nullable=True)
    motivo = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class DisponibilidadRecursoORM(Base):
    __tablename__ = "disponibilidad_recurso"
    __table_args__ = (Index("ix_disponibilidad_recurso_recurso", "recurso_id"),)
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recurso_id = Column(PGUUID(as_uuid=True), ForeignKey("recurso.id"), nullable=False)
    dia_semana = Column(SmallInteger, nullable=False)
    hora_inicio = Column(Time, nullable=False)
    hora_fin = Column(Time, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class CitaORM(Base, TimestampMixin):
    """La exclusión de solape por `recurso_id` (choque físico duro) la aplica
    un `EXCLUDE USING gist (... tstzrange(...) WITH &&)` agregado por la
    migración (requiere `btree_gist`), no declarado acá."""
    __tablename__ = "cita"
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    servicio_id = Column(PGUUID(as_uuid=True), ForeignKey("producto.id"), nullable=False)
    sucursal_id = Column(PGUUID(as_uuid=True), ForeignKey("sucursal.id"), nullable=False)
    cliente_id = Column(PGUUID(as_uuid=True), ForeignKey("cliente.id"), nullable=True)
    recurso_id = Column(PGUUID(as_uuid=True), ForeignKey("recurso.id"), nullable=True)
    empleado_id = Column(PGUUID(as_uuid=True), ForeignKey("usuario.id"), nullable=True)
    fecha_hora_inicio = Column(DateTime(timezone=True), nullable=False)
    fecha_hora_fin = Column(DateTime(timezone=True), nullable=False)
    estado = Column(String(30), nullable=False)
    disponibilidad_cruzada = Column(Boolean, default=False, nullable=False)
    politica_cancelacion_horas = Column(Integer, nullable=True)
    penalizacion_cancelacion = Column(Numeric(12, 2), nullable=True)
    motivo_cancelacion = Column(Text, nullable=True)
    venta_detalle_id = Column(PGUUID(as_uuid=True), ForeignKey("detalle_venta.id"), nullable=True)
    creado_por_usuario_id = Column(PGUUID(as_uuid=True), ForeignKey("usuario.id"), nullable=False)

    asignaciones = relationship(
        "CitaAsignacionORM", backref="cita", cascade="all, delete-orphan", lazy="selectin",
    )
    cliente = relationship("ClienteORM", viewonly=True, lazy="raise")
    empleado = relationship("UsuarioORM", viewonly=True, lazy="raise", foreign_keys=[empleado_id])


class CitaAsignacionORM(Base):
    __tablename__ = "cita_asignacion"
    __table_args__ = (
        CheckConstraint(
            "estado IN ('ofrecida', 'aceptada', 'rechazada', 'superada')",
            name="ck_cita_asignacion_estado",
        ),
        Index("ix_cita_asignacion_cita", "cita_id"),
        Index("ix_cita_asignacion_empleado_estado", "empleado_id", "estado"),
    )
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cita_id = Column(
        PGUUID(as_uuid=True), ForeignKey("cita.id", ondelete="CASCADE"), nullable=False,
    )
    empleado_id = Column(PGUUID(as_uuid=True), ForeignKey("usuario.id"), nullable=False)
    estado = Column(String(20), nullable=False)
    fecha_oferta = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    fecha_respuesta = Column(DateTime(timezone=True), nullable=True)
