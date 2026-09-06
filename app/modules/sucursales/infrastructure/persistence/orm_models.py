import uuid

from sqlalchemy import (
    Column, String, Text, Boolean, Numeric, Time, ForeignKey, CheckConstraint, Index,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship

from app.shared.infrastructure.orm_base import Base, TimestampMixin, SoftDeleteMixin

_TIPOS = ("bodega_central", "tienda", "almacen", "cedis", "oficina")


class SucursalORM(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "sucursal"
    __table_args__ = (
        CheckConstraint(
            "tipo IN ('bodega_central', 'tienda', 'almacen', 'cedis', 'oficina')",
            name="ck_sucursal_tipo",
        ),
        Index("uq_sucursal_codigo", "codigo", unique=True),
        Index("ix_sucursal_padre", "sucursal_padre_id"),
    )
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    codigo = Column(String(20), nullable=True)
    nombre = Column(String(100), nullable=False)
    tipo = Column(String(20), nullable=False)
    descripcion = Column(Text, nullable=True)
    imagen_fachada_key = Column(String(500), nullable=True)
    direccion = Column(String(255), nullable=False)
    colonia = Column(String(100), nullable=True)
    ciudad = Column(String(100), nullable=True)
    estado = Column(String(100), nullable=True)
    codigo_postal = Column(String(10), nullable=True)
    pais = Column(String(60), nullable=True)
    latitud = Column(Numeric(10, 7), nullable=True)
    longitud = Column(Numeric(10, 7), nullable=True)
    telefono = Column(String(20), nullable=False)
    email = Column(String(150), nullable=True)
    horario_apertura = Column(Time, nullable=True)
    horario_cierre = Column(Time, nullable=True)
    sucursal_padre_id = Column(
        PGUUID(as_uuid=True), ForeignKey("sucursal.id"), nullable=True
    )
    permite_ventas = Column(Boolean, nullable=False, default=True)

    padre = relationship(
        "SucursalORM", remote_side=[id], viewonly=True, lazy="raise",
    )
