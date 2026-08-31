import uuid
from sqlalchemy import Column, String, Boolean, ForeignKey, Table, Numeric
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship
from app.shared.infrastructure.orm_base import Base, TimestampMixin, SoftDeleteMixin

class CategoriaORM(Base, SoftDeleteMixin):
    __tablename__ = "categoria"
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nombre = Column(String(100), nullable=False)
    categoria_padre_id = Column(PGUUID(as_uuid=True), ForeignKey("categoria.id"), nullable=True)

class ProductoORM(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "producto"
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sku = Column(String(50), unique=True, nullable=False)
    codigo_barras = Column(String(50), unique=True, nullable=True)
    nombre = Column(String(150), nullable=False)
    descripcion = Column(String, nullable=True)
    categoria_id = Column(PGUUID(as_uuid=True), ForeignKey("categoria.id"), nullable=False)
    unidad_medida = Column(String(20), nullable=False)
    precio_venta = Column(Numeric(12, 2), nullable=False)
    costo = Column(Numeric(12, 2), nullable=False)
    impuesto_tasa = Column(Numeric(5, 2), nullable=False)
    tipo = Column(String(20), nullable=False)
    permite_stock_negativo = Column(Boolean, default=False, nullable=False)

class ProductoComponenteORM(Base):
    __tablename__ = "producto_componente"
    producto_kit_id = Column(PGUUID(as_uuid=True), ForeignKey("producto.id"), primary_key=True)
    producto_componente_id = Column(PGUUID(as_uuid=True), ForeignKey("producto.id"), primary_key=True)
    cantidad = Column(Numeric(10, 2), nullable=False)

class ExistenciaORM(Base):
    __tablename__ = "existencia"
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    producto_id = Column(PGUUID(as_uuid=True), ForeignKey("producto.id"), nullable=False)
    sucursal_id = Column(PGUUID(as_uuid=True), ForeignKey("sucursal.id"), nullable=False)
    cantidad = Column(Numeric(12, 2), default=0, nullable=False)
    stock_minimo = Column(Numeric(12, 2), default=0, nullable=False)
    stock_maximo = Column(Numeric(12, 2), nullable=True)
    updated_at = Column(TimestampMixin.updated_at.type, default=TimestampMixin.updated_at.default, onupdate=TimestampMixin.updated_at.onupdate, nullable=False)

class MovimientoInventarioORM(Base, TimestampMixin):
    __tablename__ = "movimiento_inventario"
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    producto_id = Column(PGUUID(as_uuid=True), ForeignKey("producto.id"), nullable=False)
    sucursal_id = Column(PGUUID(as_uuid=True), ForeignKey("sucursal.id"), nullable=False)
    tipo = Column(String(20), nullable=False)
    cantidad = Column(Numeric(12, 2), nullable=False)
    costo_unitario = Column(Numeric(12, 2), nullable=True)
    referencia_tipo = Column(String(20), nullable=False)
    referencia_id = Column(PGUUID(as_uuid=True), nullable=True)
    usuario_id = Column(PGUUID(as_uuid=True), ForeignKey("usuario.id"), nullable=False)
    motivo = Column(String(255), nullable=True)
