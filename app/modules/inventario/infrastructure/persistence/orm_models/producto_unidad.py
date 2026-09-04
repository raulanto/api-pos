import uuid
from sqlalchemy import (
    Column, String, ForeignKey, Numeric, CheckConstraint, UniqueConstraint, Index,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship
from app.shared.infrastructure.orm_base import Base, TimestampMixin, SoftDeleteMixin

"""
    Tabla: producto_unidad
    Descripcion: Presentaciones de venta de un producto. El stock siempre se lleva
        en unidades base sobre `producto`; cada fila acá es una presentación
        adicional ("Reja x24") con su propio `factor`, `precio_venta` y código.
    Columnas:
    - id
    - producto_id: FK a producto.id
    - nombre: "Reja x24", "Six-pack", ...
    - factor: unidades base por 1 de esta presentación (> 0)
    - precio_venta: precio de 1 presentación
    - codigo_barras: opcional, único entre presentaciones activas
    - activo, created_at, updated_at

    Restricciones:
    - ck_producto_unidad_factor_pos: factor > 0
    - uq_producto_unidad_nombre: (producto_id, nombre) no se repite entre activas
    - uq_producto_unidad_codigo_barras: codigo_barras único entre activas

    Indices:
    - ix_producto_unidad_producto: listar presentaciones de un producto
"""
class ProductoUnidadORM(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "producto_unidad"
    __table_args__ = (
        CheckConstraint("factor > 0", name="ck_producto_unidad_factor_pos"),
        Index(
            "uq_producto_unidad_nombre", "producto_id", "nombre",
            unique=True, postgresql_where=Column("activo"),
        ),
        Index(
            "uq_producto_unidad_codigo_barras", "codigo_barras",
            unique=True, postgresql_where=Column("activo"),
        ),
        Index("ix_producto_unidad_producto", "producto_id"),
    )
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    producto_id = Column(PGUUID(as_uuid=True), ForeignKey("producto.id"), nullable=False)
    nombre = Column(String(50), nullable=False)
    unidad_medida = Column(String(20), nullable=False)
    # Unidades base (del producto padre) que equivalen a 1 de esta presentación.
    #   Reja x24 sobre base "lata"  -> factor 24
    #   Lata individual sobre base "reja" (6 latas) -> factor 0.166667
    factor = Column(Numeric(12, 6), nullable=False)
    precio_venta = Column(Numeric(12, 2), nullable=False)
    codigo_barras = Column(String(50), nullable=True)

    producto = relationship("ProductoORM", viewonly=True, lazy="raise")
