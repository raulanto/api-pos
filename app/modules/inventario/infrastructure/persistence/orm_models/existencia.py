import uuid
from sqlalchemy import Column, ForeignKey, Numeric, UniqueConstraint, Index
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from app.shared.infrastructure.orm_base import Base, TimestampMixin

"""
    Tabla: existencia
    Descripcion: Saldo de stock de un producto EN CADA sucursal. Un producto tiene
        tantas filas como sucursales donde se le ha movido stock; cada fila lleva su
        propia `cantidad` y sus propios umbrales. La fila se crea de forma perezosa
        con el primer movimiento de esa sucursal (ver AplicarMovimientoUseCase).
    Columnas:
    - id: ID de la existencia.
    - producto_id: ID del producto.
    - sucursal_id: ID de la sucursal.
    - cantidad: Cantidad del producto en esa sucursal.
    - stock_minimo: Stock minimo del producto en esa sucursal.
    - stock_maximo: Stock maximo del producto en esa sucursal.
    - updated_at: Fecha de actualizacion.

    Relaciones:
    - producto_id: FK a producto.id
    - sucursal_id: FK a sucursal.id

    Indices:
    - uq_existencia_producto_sucursal: a lo sumo UNA fila de saldo por
        (producto, sucursal). Es la clave natural: `obtener`, `actualizar_cantidad`
        y `actualizar_umbrales` la asumen, y evita que dos "primeros movimientos"
        concurrentes de la misma sucursal partan el stock en dos filas.
    - ix_existencia_sucursal_id: acelera los listados por sucursal
        (`?sucursal_id=`, bajo stock por sucursal).
"""
class ExistenciaORM(Base):
    __tablename__ = "existencia"
    __table_args__ = (
        UniqueConstraint(
            "producto_id", "sucursal_id", name="uq_existencia_producto_sucursal"
        ),
        Index("ix_existencia_sucursal_id", "sucursal_id"),
    )
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    producto_id = Column(PGUUID(as_uuid=True), ForeignKey("producto.id"), nullable=False)
    sucursal_id = Column(PGUUID(as_uuid=True), ForeignKey("sucursal.id"), nullable=False)
    cantidad = Column(Numeric(12, 2), default=0, nullable=False)
    stock_minimo = Column(Numeric(12, 2), default=0, nullable=False)
    stock_maximo = Column(Numeric(12, 2), nullable=True)
    updated_at = Column(TimestampMixin.updated_at.type, default=TimestampMixin.updated_at.default, onupdate=TimestampMixin.updated_at.onupdate, nullable=False)

    # Solo lectura, para `?include=producto`.
    producto = relationship("ProductoORM", viewonly=True, lazy="raise")
