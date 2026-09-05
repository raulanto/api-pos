import uuid
from sqlalchemy import (
    Column, String, Date, Numeric, ForeignKey, CheckConstraint, Index,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship
from app.shared.infrastructure.orm_base import Base, TimestampMixin, SoftDeleteMixin

"""
    Tabla: lote
    Descripcion: Un lote es un ingreso identificable de mercadería de un producto
        (código del proveedor/fabricante) con su fecha de caducidad y su costo.
        El saldo por sucursal vive en `existencia_lote`.
    Columnas:
    - id
    - producto_id: FK a producto.id
    - codigo_lote: código del proveedor/fabricante
    - fecha_caducidad: DATE nullable (None = no vence / sin dato)
    - costo: costo unitario (unidad base) de este lote
    - proveedor: texto libre, opcional
    - activo, created_at, updated_at

    Restricciones:
    - ck_lote_costo_no_negativo: costo >= 0
    - uq_lote_producto_codigo_activo: (producto_id, codigo_lote) único entre activos

    Indices:
    - ix_lote_producto: listar lotes de un producto
    - ix_lote_caducidad: consultas de "por vencer" y orden FEFO
"""
class LoteORM(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "lote"
    __table_args__ = (
        CheckConstraint("costo >= 0", name="ck_lote_costo_no_negativo"),
        Index(
            "uq_lote_producto_codigo_activo", "producto_id", "codigo_lote",
            unique=True, postgresql_where=Column("activo"),
        ),
        Index("ix_lote_producto", "producto_id"),
        Index("ix_lote_caducidad", "fecha_caducidad"),
    )
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    producto_id = Column(PGUUID(as_uuid=True), ForeignKey("producto.id"), nullable=False)
    codigo_lote = Column(String(60), nullable=False)
    fecha_caducidad = Column(Date, nullable=True)
    costo = Column(Numeric(12, 2), nullable=False)
    proveedor = Column(String(150), nullable=True)

    producto = relationship("ProductoORM", viewonly=True, lazy="raise")
