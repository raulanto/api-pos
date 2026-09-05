import uuid
from sqlalchemy import Column, ForeignKey, Numeric, UniqueConstraint, Index
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from app.shared.infrastructure.orm_base import Base, TimestampMixin

"""
    Tabla: existencia_lote
    Descripcion: Desglose por lote del saldo de stock. Para un producto con
        control por lote, `existencia.cantidad` == suma de `existencia_lote.cantidad`
        de ese producto y sucursal.
    Columnas:
    - id
    - producto_id: FK a producto.id (redundante con lote.producto_id, para filtrar)
    - sucursal_id: FK a sucursal.id
    - lote_id: FK a lote.id
    - cantidad: saldo del lote en esa sucursal (unidad base)
    - updated_at

    Restricciones:
    - uq_existencia_lote_sucursal_lote: a lo sumo una fila por (sucursal, lote)

    Indices:
    - ix_existencia_lote_prod_suc: barrido FEFO por (producto, sucursal)
"""
class ExistenciaLoteORM(Base):
    __tablename__ = "existencia_lote"
    __table_args__ = (
        UniqueConstraint(
            "sucursal_id", "lote_id", name="uq_existencia_lote_sucursal_lote"
        ),
        Index("ix_existencia_lote_prod_suc", "producto_id", "sucursal_id"),
    )
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    producto_id = Column(PGUUID(as_uuid=True), ForeignKey("producto.id"), nullable=False)
    sucursal_id = Column(PGUUID(as_uuid=True), ForeignKey("sucursal.id"), nullable=False)
    lote_id = Column(PGUUID(as_uuid=True), ForeignKey("lote.id"), nullable=False)
    cantidad = Column(Numeric(14, 4), default=0, nullable=False)
    updated_at = Column(
        TimestampMixin.updated_at.type,
        default=TimestampMixin.updated_at.default,
        onupdate=TimestampMixin.updated_at.onupdate,
        nullable=False,
    )

    lote = relationship("LoteORM", viewonly=True, lazy="raise")
