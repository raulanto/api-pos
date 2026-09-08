import uuid

from sqlalchemy import (
    Column, String, Boolean, Integer, SmallInteger, Numeric, DateTime, Time,
    ForeignKey, CheckConstraint, UniqueConstraint, Index,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.shared.infrastructure.orm_base import Base, TimestampMixin

_TIPOS = ("nxm", "porcentaje", "precio_fijo")


class PromocionORM(Base, TimestampMixin):
    __tablename__ = "promocion"
    __table_args__ = (
        CheckConstraint("tipo IN ('nxm', 'porcentaje', 'precio_fijo')", name="ck_promocion_tipo"),
        CheckConstraint("prioridad >= 0", name="ck_promocion_prioridad"),
        Index("ix_promocion_activo", "activo"),
    )
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nombre = Column(String(120), nullable=False, unique=True)
    tipo = Column(String(20), nullable=False)
    activo = Column(Boolean, nullable=False, default=True)
    prioridad = Column(Integer, nullable=False, default=100)
    combinable = Column(Boolean, nullable=False, default=False)
    tope_descuento = Column(Numeric(12, 2), nullable=True)
    monto_minimo_compra = Column(Numeric(12, 2), nullable=True)
    metodo_pago_requerido = Column(String(20), nullable=True)
    cliente_segmento = Column(String(30), nullable=True)
    requiere_cupon = Column(Boolean, nullable=False, default=False)
    vigente_desde = Column(DateTime(timezone=True), nullable=True)
    vigente_hasta = Column(DateTime(timezone=True), nullable=True)
    hora_desde = Column(Time(), nullable=True)
    hora_hasta = Column(Time(), nullable=True)
    dias_semana = Column(SmallInteger, nullable=True)   # bitmask lun..dom = bit 0..6
    nxm_lleva = Column(Integer, nullable=True)
    nxm_paga = Column(Integer, nullable=True)
    descuento_pct = Column(Numeric(5, 2), nullable=True)
    precio_fijo = Column(Numeric(12, 2), nullable=True)
    cantidad_minima = Column(Numeric(14, 4), nullable=True)

    objetivos = relationship(
        "PromocionObjetivoORM", cascade="all, delete-orphan", lazy="selectin",
        back_populates="promocion",
    )
    sucursales = relationship(
        "PromocionSucursalORM", cascade="all, delete-orphan", lazy="selectin",
        back_populates="promocion",
    )


class PromocionSucursalORM(Base):
    """Sucursales donde aplica una promoción; sin filas = todas."""
    __tablename__ = "promocion_sucursal"
    promocion_id = Column(
        PGUUID(as_uuid=True), ForeignKey("promocion.id", ondelete="CASCADE"),
        primary_key=True,
    )
    sucursal_id = Column(
        PGUUID(as_uuid=True), ForeignKey("sucursal.id"), primary_key=True,
    )
    promocion = relationship("PromocionORM", back_populates="sucursales")


class PromocionObjetivoORM(Base):
    __tablename__ = "promocion_objetivo"
    __table_args__ = (
        CheckConstraint(
            "(producto_id IS NOT NULL)::int + (producto_unidad_id IS NOT NULL)::int "
            "+ (categoria_id IS NOT NULL)::int = 1",
            name="ck_promocion_objetivo_target",
        ),
        UniqueConstraint(
            "promocion_id", "producto_id", "producto_unidad_id", "categoria_id",
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
    categoria_id = Column(PGUUID(as_uuid=True), ForeignKey("categoria.id"), nullable=True)

    promocion = relationship("PromocionORM", back_populates="objetivos")


class CuponORM(Base, TimestampMixin):
    __tablename__ = "cupon"
    __table_args__ = (
        Index("ix_cupon_promocion", "promocion_id"),
    )
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    codigo = Column(String(40), nullable=False, unique=True)   # se guarda en MAYÚSCULAS
    promocion_id = Column(
        PGUUID(as_uuid=True), ForeignKey("promocion.id", ondelete="CASCADE"), nullable=False,
    )
    activo = Column(Boolean, nullable=False, default=True)
    vigente_desde = Column(DateTime(timezone=True), nullable=True)
    vigente_hasta = Column(DateTime(timezone=True), nullable=True)
    max_usos_total = Column(Integer, nullable=True)
    max_usos_por_persona = Column(Integer, nullable=True)


class CuponUsoORM(Base):
    __tablename__ = "cupon_uso"
    __table_args__ = (
        Index("ix_cupon_uso_cupon", "cupon_id"),
        Index("ix_cupon_uso_cupon_tel", "cupon_id", "telefono"),
        Index("ix_cupon_uso_cupon_cli", "cupon_id", "cliente_id"),
        Index("ix_cupon_uso_venta", "venta_id"),
    )
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cupon_id = Column(PGUUID(as_uuid=True), ForeignKey("cupon.id", ondelete="CASCADE"), nullable=False)
    venta_id = Column(PGUUID(as_uuid=True), ForeignKey("venta.id"), nullable=False)
    telefono = Column(String(50), nullable=True)
    cliente_id = Column(PGUUID(as_uuid=True), nullable=True)
    monto_descontado = Column(Numeric(12, 2), nullable=False)
    usado_en = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
