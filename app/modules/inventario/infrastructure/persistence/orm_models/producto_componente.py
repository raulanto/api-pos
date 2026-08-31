from sqlalchemy import Column, ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from app.shared.infrastructure.orm_base import Base

"""
    Tabla: producto_componente
    Descripcion: Tabla que almacena los componentes de los productos.
    Columnas:
    - producto_kit_id: ID del producto kit.
    - producto_componente_id: ID del producto componente.
    - cantidad: Cantidad del producto componente.
    
    Relaciones:
    - producto_kit_id: FK a producto.id
    - producto_componente_id: FK a producto.id

"""
class ProductoComponenteORM(Base):
    __tablename__ = "producto_componente"
    producto_kit_id = Column(PGUUID(as_uuid=True), ForeignKey("producto.id"), primary_key=True)
    producto_componente_id = Column(PGUUID(as_uuid=True), ForeignKey("producto.id"), primary_key=True)
    cantidad = Column(Numeric(10, 2), nullable=False)
