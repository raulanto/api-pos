import uuid
from sqlalchemy import Column, ForeignKey, Numeric
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from app.shared.infrastructure.orm_base import Base, TimestampMixin

"""
    Tabla: existencia
    Descripcion: Tabla que almacena la existencia de los productos en las sucursales.
    Columnas:
    - id: ID de la existencia.
    - producto_id: ID del producto.
    - sucursal_id: ID de la sucursal.
    - cantidad: Cantidad del producto.
    - stock_minimo: Stock minimo del producto.
    - stock_maximo: Stock maximo del producto.
    - updated_at: Fecha de actualizacion.

    Relaciones:
    - producto_id: FK a producto.id
    - sucursal_id: FK a sucursal.id
"""
class ExistenciaORM(Base):
    __tablename__ = "existencia"
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    producto_id = Column(PGUUID(as_uuid=True), ForeignKey("producto.id"), nullable=False)
    sucursal_id = Column(PGUUID(as_uuid=True), ForeignKey("sucursal.id"), nullable=False)
    cantidad = Column(Numeric(12, 2), default=0, nullable=False)
    stock_minimo = Column(Numeric(12, 2), default=0, nullable=False)
    stock_maximo = Column(Numeric(12, 2), nullable=True)
    updated_at = Column(TimestampMixin.updated_at.type, default=TimestampMixin.updated_at.default, onupdate=TimestampMixin.updated_at.onupdate, nullable=False)

    # Solo lectura, para `?include=producto`.
    producto = relationship("ProductoORM", viewonly=True, lazy="raise")
