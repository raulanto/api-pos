import uuid
from sqlalchemy import Column, String, ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship
from app.shared.infrastructure.orm_base import Base, TimestampMixin

"""
    Tabla: movimiento_inventario
    Descripcion: Tabla que almacena los movimientos de inventario.
    Columnas:
    - id: ID del movimiento.
    - producto_id: ID del producto.
    - sucursal_id: ID de la sucursal.
    - tipo: Tipo de movimiento.
    - cantidad: Cantidad del movimiento.
    - costo_unitario: Costo unitario del movimiento.
    - referencia_tipo: Tipo de referencia.
    - referencia_id: ID de la referencia.
    - usuario_id: ID del usuario.
    - motivo: Motivo del movimiento.
    - created_at: Fecha de creacion.
    - updated_at: Fecha de actualizacion.

    Relaciones:
    - producto_id: FK a producto.id
    - sucursal_id: FK a sucursal.id
    - usuario_id: FK a usuario.id
"""
class MovimientoInventarioORM(Base, TimestampMixin):
    __tablename__ = "movimiento_inventario"
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    producto_id = Column(PGUUID(as_uuid=True), ForeignKey("producto.id"), nullable=False)
    sucursal_id = Column(PGUUID(as_uuid=True), ForeignKey("sucursal.id"), nullable=False)
    tipo = Column(String(20), nullable=False)
    cantidad = Column(Numeric(14, 4), nullable=False)
    costo_unitario = Column(Numeric(12, 2), nullable=True)
    referencia_tipo = Column(String(20), nullable=False)
    referencia_id = Column(PGUUID(as_uuid=True), nullable=True)
    usuario_id = Column(PGUUID(as_uuid=True), ForeignKey("usuario.id"), nullable=False)
    motivo = Column(String(255), nullable=True)
    # Trazabilidad: presentación y cantidad tal como se capturaron, antes de
    # convertir a la unidad base (`cantidad`). NULL => se capturó en unidad base.
    unidad_capturada_id = Column(
        PGUUID(as_uuid=True), ForeignKey("producto_unidad.id"), nullable=True
    )
    cantidad_capturada = Column(Numeric(14, 4), nullable=True)
    # Lote afectado (productos con control por lote). NULL = sin control por lote.
    lote_id = Column(PGUUID(as_uuid=True), ForeignKey("lote.id"), nullable=True)

    # Solo lectura, para `?include=producto,usuario`.
    producto = relationship("ProductoORM", viewonly=True, lazy="raise")
    usuario = relationship("UsuarioORM", viewonly=True, lazy="raise")
