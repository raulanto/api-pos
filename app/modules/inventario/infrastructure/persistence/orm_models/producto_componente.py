from sqlalchemy import Column, ForeignKey, Numeric, CheckConstraint, Index
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship
from app.shared.infrastructure.orm_base import Base

"""
    Tabla: producto_componente
    Descripcion: Receta (BOM) de un producto kit. Cada fila dice que una unidad de
        `producto_kit_id` consume `cantidad` unidades de `producto_componente_id`.
    Columnas:
    - producto_kit_id: ID del producto kit.
    - producto_componente_id: ID del producto componente.
    - cantidad: Unidades del componente por unidad de kit (> 0).

    Relaciones:
    - producto_kit_id: FK a producto.id
    - producto_componente_id: FK a producto.id

    Restricciones:
    - PK (producto_kit_id, producto_componente_id): no se repite un componente en un kit.
    - ck_producto_componente_cantidad_pos: cantidad > 0.
    - ck_producto_componente_distinto: un producto no puede ser componente de sí mismo.

    Indices:
    - ix_producto_componente_componente: acelera "¿este producto es componente de algún kit?".
"""
class ProductoComponenteORM(Base):
    __tablename__ = "producto_componente"
    __table_args__ = (
        CheckConstraint("cantidad > 0", name="ck_producto_componente_cantidad_pos"),
        CheckConstraint(
            "producto_kit_id <> producto_componente_id",
            name="ck_producto_componente_distinto",
        ),
        Index("ix_producto_componente_componente", "producto_componente_id"),
    )
    producto_kit_id = Column(PGUUID(as_uuid=True), ForeignKey("producto.id"), primary_key=True)
    producto_componente_id = Column(PGUUID(as_uuid=True), ForeignKey("producto.id"), primary_key=True)
    cantidad = Column(Numeric(10, 2), nullable=False)

    # Solo lectura, para `?include=producto` sobre la línea del kit.
    producto = relationship(
        "ProductoORM",
        primaryjoin="ProductoComponenteORM.producto_componente_id == ProductoORM.id",
        viewonly=True,
        lazy="raise",
    )
