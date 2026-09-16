import uuid
from sqlalchemy import (
    Column, String, Text, Boolean, Integer, Numeric, DateTime, Date,
    ForeignKey, CheckConstraint, Index, UniqueConstraint, text,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID, ARRAY
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.shared.infrastructure.orm_base import Base, TimestampMixin


class ProveedorORM(Base, TimestampMixin):
    __tablename__ = "proveedor"
    __table_args__ = (
        Index(
            "uq_proveedor_codigo_activo", "codigo",
            unique=True, postgresql_where=Column("activo"),
        ),
        CheckConstraint("tipo_persona IN ('fisica', 'moral')", name="ck_proveedor_tipo_persona"),
        CheckConstraint(
            "condiciones_pago IN ('contado', 'credito')", name="ck_proveedor_condiciones_pago",
        ),
    )
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    codigo = Column(String(30), nullable=False)
    razon_social = Column(String(200), nullable=False)
    nombre_comercial = Column(String(200), nullable=True)
    rfc = Column(String(20), nullable=True)
    tipo_persona = Column(String(10), nullable=False)
    condiciones_pago = Column(String(10), nullable=False)
    dias_credito = Column(Integer, nullable=True)
    moneda = Column(String(3), nullable=False, default="MXN")
    contacto_principal = Column(String(150), nullable=True)
    telefono = Column(String(30), nullable=True)
    email = Column(String(150), nullable=True)
    direccion_calle = Column(String(200), nullable=True)
    direccion_numero = Column(String(30), nullable=True)
    direccion_colonia = Column(String(120), nullable=True)
    direccion_ciudad = Column(String(120), nullable=True)
    direccion_estado = Column(String(120), nullable=True)
    direccion_codigo_postal = Column(String(15), nullable=True)
    activo = Column(Boolean, nullable=False, default=True)
    notas = Column(Text, nullable=True)


class ProductoProveedorORM(Base, TimestampMixin):
    __tablename__ = "producto_proveedor"
    __table_args__ = (
        UniqueConstraint("producto_id", "proveedor_id", name="uq_producto_proveedor"),
        Index(
            "uq_producto_proveedor_principal", "producto_id",
            unique=True, postgresql_where=text("es_proveedor_principal AND activo"),
        ),
    )
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    producto_id = Column(PGUUID(as_uuid=True), ForeignKey("producto.id"), nullable=False)
    proveedor_id = Column(PGUUID(as_uuid=True), ForeignKey("proveedor.id"), nullable=False)
    codigo_proveedor = Column(String(60), nullable=True)
    precio_compra = Column(Numeric(12, 2), nullable=False)
    tiempo_entrega_dias = Column(Integer, nullable=False)
    stock_minimo = Column(Numeric(14, 4), nullable=False)
    stock_maximo = Column(Numeric(14, 4), nullable=True)
    cantidad_reorden = Column(Numeric(14, 4), nullable=False)
    es_proveedor_principal = Column(Boolean, nullable=False, default=False)
    activo = Column(Boolean, nullable=False, default=True)


class PedidoProveedorORM(Base, TimestampMixin):
    __tablename__ = "pedido_proveedor"
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    proveedor_id = Column(PGUUID(as_uuid=True), ForeignKey("proveedor.id"), nullable=False)
    sucursal_id = Column(PGUUID(as_uuid=True), ForeignKey("sucursal.id"), nullable=False)
    estado = Column(String(20), nullable=False)
    generado_automaticamente = Column(Boolean, nullable=False, default=False)
    generado_por = Column(PGUUID(as_uuid=True), ForeignKey("usuario.id"), nullable=True)
    confirmado_por = Column(PGUUID(as_uuid=True), ForeignKey("usuario.id"), nullable=True)
    fecha_pedido = Column(DateTime(timezone=True), nullable=False)
    fecha_estimada_entrega = Column(Date, nullable=True)
    notas = Column(Text, nullable=True)

    lineas = relationship(
        "PedidoProveedorLineaORM", backref="pedido", cascade="all, delete-orphan",
        lazy="selectin",
    )
    proveedor = relationship("ProveedorORM", viewonly=True, lazy="raise")


class PedidoProveedorLineaORM(Base):
    __tablename__ = "pedido_proveedor_detalle"
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pedido_id = Column(
        PGUUID(as_uuid=True), ForeignKey("pedido_proveedor.id", ondelete="CASCADE"),
        nullable=False,
    )
    producto_id = Column(PGUUID(as_uuid=True), ForeignKey("producto.id"), nullable=False)
    cantidad_solicitada = Column(Numeric(14, 4), nullable=False)
    cantidad_recibida = Column(Numeric(14, 4), nullable=False, default=0)
    precio_unitario = Column(Numeric(12, 2), nullable=False)


class RecepcionProveedorORM(Base):
    __tablename__ = "recepcion_proveedor"
    __table_args__ = (
        CheckConstraint(
            "estado IN ('completa', 'parcial', 'con_defectos')", name="ck_recepcion_estado",
        ),
    )
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pedido_id = Column(PGUUID(as_uuid=True), ForeignKey("pedido_proveedor.id"), nullable=True)
    proveedor_id = Column(PGUUID(as_uuid=True), ForeignKey("proveedor.id"), nullable=False)
    sucursal_id = Column(PGUUID(as_uuid=True), ForeignKey("sucursal.id"), nullable=False)
    numero_factura = Column(String(60), nullable=True)
    numero_remision = Column(String(60), nullable=True)
    transportista = Column(String(120), nullable=True)
    recibido_por = Column(PGUUID(as_uuid=True), ForeignKey("usuario.id"), nullable=False)
    fecha_recepcion = Column(DateTime(timezone=True), nullable=False)
    estado = Column(String(20), nullable=False)
    notas = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    lineas = relationship(
        "RecepcionProveedorLineaORM", backref="recepcion", cascade="all, delete-orphan",
        lazy="selectin",
    )


class RecepcionProveedorLineaORM(Base):
    __tablename__ = "recepcion_proveedor_detalle"
    __table_args__ = (
        CheckConstraint(
            "motivo_defecto IS NULL OR motivo_defecto IN "
            "('danado', 'caducado', 'incompleto', 'error_proveedor', 'otro')",
            name="ck_recepcion_detalle_motivo",
        ),
        CheckConstraint(
            "accion_defecto IS NULL OR accion_defecto IN "
            "('devolucion', 'merma', 'aceptado_con_descuento')",
            name="ck_recepcion_detalle_accion",
        ),
    )
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recepcion_id = Column(
        PGUUID(as_uuid=True), ForeignKey("recepcion_proveedor.id", ondelete="CASCADE"),
        nullable=False,
    )
    producto_id = Column(PGUUID(as_uuid=True), ForeignKey("producto.id"), nullable=False)
    cantidad_esperada = Column(Numeric(14, 4), nullable=True)
    cantidad_recibida_buena = Column(Numeric(14, 4), nullable=False)
    cantidad_defectuosa = Column(Numeric(14, 4), nullable=False, default=0)
    motivo_defecto = Column(String(20), nullable=True)
    accion_defecto = Column(String(25), nullable=True)
    fotos_evidencia_keys = Column(ARRAY(String), nullable=True)
    notas = Column(Text, nullable=True)


class DevolucionProveedorORM(Base, TimestampMixin):
    __tablename__ = "devolucion_proveedor"
    __table_args__ = (
        CheckConstraint(
            "estado IN ('pendiente', 'enviada', 'cerrada')", name="ck_devolucion_prov_estado",
        ),
        CheckConstraint(
            "resultado IS NULL OR resultado IN ('aceptada_proveedor', 'rechazada_proveedor')",
            name="ck_devolucion_prov_resultado",
        ),
        CheckConstraint(
            "tipo_resolucion IS NULL OR tipo_resolucion IN "
            "('reemplazo', 'nota_credito', 'reembolso')",
            name="ck_devolucion_prov_resolucion",
        ),
    )
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    proveedor_id = Column(PGUUID(as_uuid=True), ForeignKey("proveedor.id"), nullable=False)
    recepcion_id = Column(PGUUID(as_uuid=True), ForeignKey("recepcion_proveedor.id"), nullable=False)
    creado_por = Column(PGUUID(as_uuid=True), ForeignKey("usuario.id"), nullable=False)
    estado = Column(String(20), nullable=False)
    resultado = Column(String(20), nullable=True)
    tipo_resolucion = Column(String(20), nullable=True)
    fecha_envio = Column(DateTime(timezone=True), nullable=True)
    fecha_cierre = Column(DateTime(timezone=True), nullable=True)
    notas = Column(Text, nullable=True)

    lineas = relationship(
        "DevolucionProveedorLineaORM", backref="devolucion", cascade="all, delete-orphan",
        lazy="selectin",
    )


class DevolucionProveedorLineaORM(Base):
    __tablename__ = "devolucion_proveedor_detalle"
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    devolucion_id = Column(
        PGUUID(as_uuid=True), ForeignKey("devolucion_proveedor.id", ondelete="CASCADE"),
        nullable=False,
    )
    recepcion_detalle_id = Column(
        PGUUID(as_uuid=True), ForeignKey("recepcion_proveedor_detalle.id"), nullable=False,
    )
    producto_id = Column(PGUUID(as_uuid=True), ForeignKey("producto.id"), nullable=False)
    cantidad = Column(Numeric(14, 4), nullable=False)
