import uuid
from sqlalchemy import (
    Column, String, Numeric, ForeignKey, CheckConstraint, Index, DateTime,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.shared.infrastructure.orm_base import Base, TimestampMixin

"""
    Tabla: instancia_abierta
    Descripcion: Un envase físico destapado de un producto fraccionable, con su
        saldo restante en unidad base. El total en unidad base sigue en
        `existencia`; esta tabla solo rastrea "cuánto queda en este envase".
    Columnas:
    - id
    - producto_id: FK a producto.id
    - sucursal_id: FK a sucursal.id
    - producto_unidad_id: FK a producto_unidad.id (presentación origen, nullable)
    - lote_id: FK a lote.id (contenido, nullable)
    - capacidad_inicial: contenido al abrir (unidad base, > 0)
    - saldo: contenido restante (0 <= saldo <= capacidad_inicial)
    - estado: abierta | agotada | descartada
    - abierta_por: FK a usuario.id
    - abierta_at, cerrada_at, motivo_cierre
    - created_at, updated_at

    Restricciones:
    - ck_instancia_capacidad_positiva: capacidad_inicial > 0
    - ck_instancia_saldo_rango: saldo >= 0 AND saldo <= capacidad_inicial

    Indices:
    - ix_instancia_abierta_producto_sucursal
    - ix_instancia_abierta_estado
    - ix_instancia_abierta_lote
    - ix_instancia_abierta_abiertas: parcial WHERE estado='abierta', para el
      plan de consumo FIFO por abierta_at.
"""
class InstanciaAbiertaORM(Base, TimestampMixin):
    __tablename__ = "instancia_abierta"
    __table_args__ = (
        CheckConstraint(
            "capacidad_inicial > 0", name="ck_instancia_capacidad_positiva"
        ),
        CheckConstraint(
            "saldo >= 0 AND saldo <= capacidad_inicial", name="ck_instancia_saldo_rango"
        ),
        Index(
            "ix_instancia_abierta_producto_sucursal", "producto_id", "sucursal_id"
        ),
        Index("ix_instancia_abierta_estado", "estado"),
        Index("ix_instancia_abierta_lote", "lote_id"),
        Index(
            "ix_instancia_abierta_abiertas",
            "producto_id", "sucursal_id", "abierta_at",
            postgresql_where=Column("estado") == "abierta",
        ),
    )
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    producto_id = Column(PGUUID(as_uuid=True), ForeignKey("producto.id"), nullable=False)
    sucursal_id = Column(PGUUID(as_uuid=True), ForeignKey("sucursal.id"), nullable=False)
    producto_unidad_id = Column(
        PGUUID(as_uuid=True), ForeignKey("producto_unidad.id"), nullable=True
    )
    lote_id = Column(PGUUID(as_uuid=True), ForeignKey("lote.id"), nullable=True)
    capacidad_inicial = Column(Numeric(14, 4), nullable=False)
    saldo = Column(Numeric(14, 4), nullable=False)
    estado = Column(String(12), nullable=False)
    abierta_por = Column(PGUUID(as_uuid=True), ForeignKey("usuario.id"), nullable=False)
    abierta_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    cerrada_at = Column(DateTime(timezone=True), nullable=True)
    motivo_cierre = Column(String(255), nullable=True)

    producto = relationship("ProductoORM", viewonly=True, lazy="raise")
    lote = relationship("LoteORM", viewonly=True, lazy="raise")
