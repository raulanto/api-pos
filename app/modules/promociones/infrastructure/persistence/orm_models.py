import uuid

from sqlalchemy import (
    Column, String, Boolean, Integer, Numeric, DateTime, ForeignKey,
    CheckConstraint, UniqueConstraint, Index,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship

from app.shared.infrastructure.orm_base import Base, TimestampMixin

_TIPOS = ("nxm", "porcentaje", "precio_fijo")


class PromocionORM(Base, TimestampMixin):
    __tablename__ = "promocion"
    __table_args__ = (
        CheckConstraint("tipo IN ('nxm', 'porcentaje', 'precio_fijo')", name="ck_promocion_tipo"),
        CheckConstraint("prioridad >= 0", name="ck_promocion_prioridad"),
        Index("ix_promocion_activo", "activo"),
        Index("ix_promocion_sucursal", "sucursal_id"),
    )
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nombre = Column(String(120), nullable=False, unique=True)
    tipo = Column(String(20), nullable=False)
    activo = Column(Boolean, nullable=False, default=True)
    prioridad = Column(Integer, nullable=False, default=100)
    sucursal_id = Column(PGUUID(as_uuid=True), ForeignKey("sucursal.id"), nullable=True)
    vigente_desde = Column(DateTime(timezone=True), nullable=True)
    vigente_hasta = Column(DateTime(timezone=True), nullable=True)
    nxm_lleva = Column(Integer, nullable=True)
    nxm_paga = Column(Integer, nullable=True)
    descuento_pct = Column(Numeric(5, 2), nullable=True)
    precio_fijo = Column(Numeric(12, 2), nullable=True)
    cantidad_minima = Column(Numeric(14, 4), nullable=True)

    objetivos = relationship(
        "PromocionObjetivoORM", cascade="all, delete-orphan", lazy="selectin",
        back_populates="promocion",
    )


class PromocionObjetivoORM(Base):
    __tablename__ = "promocion_objetivo"
    __table_args__ = (
        CheckConstraint(
            "producto_id IS NOT NULL OR producto_unidad_id IS NOT NULL",
            name="ck_promocion_objetivo_target",
        ),
        UniqueConstraint(
            "promocion_id", "producto_id", "producto_unidad_id",
            name="uq_promocion_objetivo",
        ),
        Index("ix_promocion_objetivo_promocion", "promocion_id"),
    )
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    promocion_id = Column(
        PGUUID(as_uuid=True), ForeignKey("promocion.id", ondelete="CASCADE"), nullable=False
    )
    producto_id = Column(PGUUID(as_uuid=True), ForeignKey("producto.id"), nullable=True)
    producto_unidad_id = Column(
        PGUUID(as_uuid=True), ForeignKey("producto_unidad.id"), nullable=True
    )

    promocion = relationship("PromocionORM", back_populates="objetivos")
