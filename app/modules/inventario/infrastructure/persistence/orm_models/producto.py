import uuid
from sqlalchemy import Column, String, Boolean, ForeignKey, Numeric, Index
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship
from app.shared.infrastructure.orm_base import Base, TimestampMixin, SoftDeleteMixin


"""
    Tabla: producto
    Descripcion: Tabla que almacena los productos.
    Columnas:
    - id: ID del producto.
    - sku: SKU del producto.
    - codigo_barras: Codigo de barras del producto.
    - nombre: Nombre del producto.
    - descripcion: Descripcion del producto.
    - categoria_id: ID de la categoria.
    - unidad_medida: Unidad de medida del producto.
    - precio_venta: Precio de venta del producto.
    - costo: Costo del producto.
    - impuesto_tasa: Tasa de impuesto del producto.
    - tipo: Tipo de producto.
    - permite_stock_negativo: Permite stock negativo.
    - created_at: Fecha de creacion.
    - updated_at: Fecha de actualizacion.
    - deleted_at: Fecha de eliminacion.

    Relaciones:
    - categoria_id: FK a categoria.id
    - existencias: 1:N con existencia.producto_id
    - movimientos: 1:N con movimiento_inventario.producto_id
    - componentes: 1:N con producto_componente.producto_kit_id

    Indices:
    - uq_producto_sku_activo: SKU y codigo de barras son únicos SOLO entre productos activos: un producto
        dado de baja libera su SKU/código para que pueda reutilizarse.


"""
class ProductoORM(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "producto"
    __table_args__ = (
        Index(
            "uq_producto_sku_activo", "sku",
            unique=True, postgresql_where=Column("activo"),
        ),
        Index(
            "uq_producto_codigo_barras_activo", "codigo_barras",
            unique=True, postgresql_where=Column("activo"),
        ),
    )
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sku = Column(String(50), nullable=False)
    codigo_barras = Column(String(50), nullable=True)
    nombre = Column(String(150), nullable=False)
    descripcion = Column(String, nullable=True)
    categoria_id = Column(PGUUID(as_uuid=True), ForeignKey("categoria.id"), nullable=False)
    unidad_medida = Column(String(20), nullable=False)
    precio_venta = Column(Numeric(12, 2), nullable=False)
    costo = Column(Numeric(12, 2), nullable=False)
    impuesto_tasa = Column(Numeric(5, 2), nullable=False)
    tipo = Column(String(20), nullable=False)
    permite_stock_negativo = Column(Boolean, default=False, nullable=False)

    # Solo lectura, para `?include=categoria,existencias,componentes`.
    categoria = relationship("CategoriaORM", viewonly=True, lazy="raise")
    existencias = relationship(
        "ExistenciaORM",
        primaryjoin="ProductoORM.id == foreign(ExistenciaORM.producto_id)",
        viewonly=True,
        lazy="raise",
    )
    # Líneas de receta cuando este producto es un kit (`?include=componentes`).
    componentes = relationship(
        "ProductoComponenteORM",
        primaryjoin="ProductoORM.id == foreign(ProductoComponenteORM.producto_kit_id)",
        viewonly=True,
        lazy="raise",
    )
    # Presentaciones de venta adicionales (`?include=unidades`).
    unidades = relationship(
        "ProductoUnidadORM",
        primaryjoin="ProductoORM.id == foreign(ProductoUnidadORM.producto_id)",
        viewonly=True,
        lazy="raise",
    )
