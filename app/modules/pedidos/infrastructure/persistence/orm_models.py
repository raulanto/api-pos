import uuid

from sqlalchemy import (
    Column, String, Text, Boolean, ForeignKey, Numeric, DateTime,
    CheckConstraint, Index,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.shared.infrastructure.orm_base import Base, TimestampMixin

_TIPOS = "('mostrador', 'domicilio', 'recoger')"
_CANALES = "('pos', 'web', 'telefono')"
_ESTADOS = "('borrador', 'confirmado', 'facturado', 'cancelado')"
_ESTADOS_ENTREGA = "('pendiente', 'en_preparacion', 'en_reparto', 'entregado', 'fallido')"


class PedidoORM(Base, TimestampMixin):
    __tablename__ = "pedido"
    __table_args__ = (
        CheckConstraint(f"tipo IN {_TIPOS}", name="ck_pedido_tipo"),
        CheckConstraint(f"canal IN {_CANALES}", name="ck_pedido_canal"),
        CheckConstraint(f"estado IN {_ESTADOS}", name="ck_pedido_estado"),
        CheckConstraint(
            f"estado_entrega IS NULL OR estado_entrega IN {_ESTADOS_ENTREGA}",
            name="ck_pedido_estado_entrega",
        ),
        Index("ix_pedido_sucursal_estado", "sucursal_id", "estado"),
        Index("ix_pedido_cliente", "cliente_id"),
        Index("ix_pedido_telefono", "telefono"),
        Index("ix_pedido_repartidor", "repartidor_id"),
        Index("ix_pedido_estado_entrega", "estado_entrega"),
    )
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sucursal_id = Column(PGUUID(as_uuid=True), ForeignKey("sucursal.id"), nullable=False)
    usuario_id = Column(PGUUID(as_uuid=True), ForeignKey("usuario.id"), nullable=False)
    cliente_id = Column(PGUUID(as_uuid=True), ForeignKey("cliente.id"), nullable=True)
    tipo = Column(String(20), nullable=False)
    canal = Column(String(20), nullable=False)
    estado = Column(String(20), nullable=False)
    estado_entrega = Column(String(20), nullable=True)
    telefono = Column(String(50), nullable=True)
    descuento_total = Column(Numeric(12, 2), nullable=False, default=0)
    motivo_descuento = Column(Text, nullable=True)
    codigo_cupon = Column(String(40), nullable=True)
    cliente_segmento = Column(String(60), nullable=True)
    notas = Column(Text, nullable=True)
    fecha_promesa = Column(DateTime(timezone=True), nullable=True)
    # Entrega
    direccion_texto = Column(Text, nullable=True)
    referencia_direccion = Column(Text, nullable=True)
    repartidor_id = Column(PGUUID(as_uuid=True), ForeignKey("usuario.id"), nullable=True)
    entrega_fallo_motivo = Column(Text, nullable=True)
    despachado_en = Column(DateTime(timezone=True), nullable=True)
    entregado_en = Column(DateTime(timezone=True), nullable=True)
    # Cierre
    venta_id = Column(PGUUID(as_uuid=True), ForeignKey("venta.id"), nullable=True)
    idempotency_key = Column(String(80), nullable=True, unique=True)

    lineas = relationship(
        "DetallePedidoORM", backref="pedido", cascade="all, delete-orphan",
        lazy="selectin",
    )
    pagos = relationship(
        "PedidoPagoORM", backref="pedido", cascade="all, delete-orphan",
        lazy="selectin",
    )
    # ponytail: sin relaciones `?include=` (cliente/repartidor). El response trae
    # los ids; agregar embeds si el front los pide seguido.


class DetallePedidoORM(Base):
    __tablename__ = "detalle_pedido"
    __table_args__ = (
        Index("ix_detalle_pedido_pedido", "pedido_id"),
        Index("ix_detalle_pedido_asignado", "asignado_a"),
    )
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pedido_id = Column(
        PGUUID(as_uuid=True), ForeignKey("pedido.id", ondelete="CASCADE"), nullable=False,
    )
    producto_id = Column(PGUUID(as_uuid=True), ForeignKey("producto.id"), nullable=False)
    cantidad = Column(Numeric(14, 4), nullable=False)
    precio_unitario = Column(Numeric(12, 2), nullable=False)
    descuento_linea = Column(Numeric(12, 2), nullable=False, default=0)
    impuesto_tasa = Column(Numeric(5, 2), nullable=False, default=0)
    producto_unidad_id = Column(
        PGUUID(as_uuid=True), ForeignKey("producto_unidad.id"), nullable=True,
    )
    cantidad_en_unidad_base = Column(Numeric(14, 4), nullable=True)
    promo_id = Column(PGUUID(as_uuid=True), ForeignKey("promocion.id"), nullable=True)
    promo_etiqueta = Column(String(120), nullable=True)
    promo_descuento = Column(Numeric(12, 2), nullable=False, default=0)
    # Servicio (envío, instalación, …): lo marca el backend según el tipo del
    # producto; `asignado_a` es la persona responsable (obligatoria para confirmar).
    es_servicio = Column(Boolean, nullable=False, default=False)
    asignado_a = Column(PGUUID(as_uuid=True), ForeignKey("usuario.id"), nullable=True)


class PedidoPagoORM(Base):
    """Anticipo / prepago de un pedido (append-only salvo el flag `reembolsado`)."""
    __tablename__ = "pedido_pago"
    __table_args__ = (
        CheckConstraint("monto > 0", name="ck_pedido_pago_monto_pos"),
        Index("ix_pedido_pago_pedido", "pedido_id"),
    )
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pedido_id = Column(
        PGUUID(as_uuid=True), ForeignKey("pedido.id", ondelete="CASCADE"), nullable=False,
    )
    monto = Column(Numeric(12, 2), nullable=False)
    metodo_pago = Column(String(50), nullable=False)
    referencia = Column(String(120), nullable=True)
    reembolsado = Column(Boolean, nullable=False, default=False)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )
