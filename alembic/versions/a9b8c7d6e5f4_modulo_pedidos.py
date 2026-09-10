"""modulo pedidos: ordenes, cotizaciones y envio a domicilio

- Tabla `pedido` (cabecera: tipo mostrador/domicilio/recoger, canal, estado
  borrador/confirmado/facturado/cancelado, estado_entrega, datos de envío,
  `costo_envio`, `codigo_cupon`, `venta_id` al facturar, idempotencia).
- Tabla `detalle_pedido` (líneas con precio congelado: mayoreo/promo/unidad base).
- Tabla `pedido_pago` (anticipos / prepago; `reembolsado` al cancelar).
- Permisos `pedidos.crear|leer|editar|confirmar|facturar|cancelar|repartir`
  -> roles admin, gerente, cajero (repartir: admin, gerente, repartidor).

Revision ID: a9b8c7d6e5f4
Revises: d56709572ca2
Create Date: 2026-09-09 00:00:00.000000
"""
from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PGUUID


revision: str = "a9b8c7d6e5f4"
down_revision: Union[str, Sequence[str], None] = "d56709572ca2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TIPOS = "('mostrador', 'domicilio', 'recoger')"
_CANALES = "('pos', 'web', 'telefono')"
_ESTADOS = "('borrador', 'confirmado', 'facturado', 'cancelado')"
_ESTADOS_ENTREGA = "('pendiente', 'en_preparacion', 'en_reparto', 'entregado', 'fallido')"

# (codigo, descripcion, roles)
_TODOS = ("admin", "gerente", "cajero")
_PERMISOS = [
    ("pedidos.crear", "Crear pedidos / cotizaciones", _TODOS),
    ("pedidos.leer", "Ver pedidos y su tablero", _TODOS + ("repartidor",)),
    ("pedidos.editar", "Editar un pedido en borrador y registrar anticipos", _TODOS),
    ("pedidos.confirmar", "Confirmar un pedido (congelar precio)", _TODOS),
    ("pedidos.facturar", "Facturar un pedido confirmado (emitir la venta)", _TODOS),
    ("pedidos.cancelar", "Cancelar un pedido", _TODOS),
    ("pedidos.repartir", "Asignar repartidor y avanzar la entrega", ("admin", "gerente", "repartidor")),
]


def upgrade() -> None:
    op.create_table(
        "pedido",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column("sucursal_id", PGUUID(as_uuid=True), sa.ForeignKey("sucursal.id"), nullable=False),
        sa.Column("usuario_id", PGUUID(as_uuid=True), sa.ForeignKey("usuario.id"), nullable=False),
        sa.Column("cliente_id", PGUUID(as_uuid=True), sa.ForeignKey("cliente.id"), nullable=True),
        sa.Column("tipo", sa.String(length=20), nullable=False),
        sa.Column("canal", sa.String(length=20), nullable=False),
        sa.Column("estado", sa.String(length=20), nullable=False),
        sa.Column("estado_entrega", sa.String(length=20), nullable=True),
        sa.Column("telefono", sa.String(length=50), nullable=True),
        sa.Column("descuento_total", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("motivo_descuento", sa.Text(), nullable=True),
        sa.Column("costo_envio", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("codigo_cupon", sa.String(length=40), nullable=True),
        sa.Column("cliente_segmento", sa.String(length=60), nullable=True),
        sa.Column("notas", sa.Text(), nullable=True),
        sa.Column("fecha_promesa", sa.DateTime(timezone=True), nullable=True),
        sa.Column("direccion_texto", sa.Text(), nullable=True),
        sa.Column("referencia_direccion", sa.Text(), nullable=True),
        sa.Column("repartidor_id", PGUUID(as_uuid=True), sa.ForeignKey("usuario.id"), nullable=True),
        sa.Column("entrega_fallo_motivo", sa.Text(), nullable=True),
        sa.Column("despachado_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("entregado_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("venta_id", PGUUID(as_uuid=True), sa.ForeignKey("venta.id"), nullable=True),
        sa.Column("idempotency_key", sa.String(length=80), nullable=True, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(f"tipo IN {_TIPOS}", name="ck_pedido_tipo"),
        sa.CheckConstraint(f"canal IN {_CANALES}", name="ck_pedido_canal"),
        sa.CheckConstraint(f"estado IN {_ESTADOS}", name="ck_pedido_estado"),
        sa.CheckConstraint(
            f"estado_entrega IS NULL OR estado_entrega IN {_ESTADOS_ENTREGA}",
            name="ck_pedido_estado_entrega",
        ),
    )
    for col in ("descuento_total", "costo_envio"):
        op.alter_column("pedido", col, server_default=None)
    op.create_index("ix_pedido_sucursal_estado", "pedido", ["sucursal_id", "estado"])
    op.create_index("ix_pedido_cliente", "pedido", ["cliente_id"])
    op.create_index("ix_pedido_telefono", "pedido", ["telefono"])
    op.create_index("ix_pedido_repartidor", "pedido", ["repartidor_id"])
    op.create_index("ix_pedido_estado_entrega", "pedido", ["estado_entrega"])

    op.create_table(
        "detalle_pedido",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column("pedido_id", PGUUID(as_uuid=True), sa.ForeignKey("pedido.id", ondelete="CASCADE"), nullable=False),
        sa.Column("producto_id", PGUUID(as_uuid=True), sa.ForeignKey("producto.id"), nullable=False),
        sa.Column("cantidad", sa.Numeric(14, 4), nullable=False),
        sa.Column("precio_unitario", sa.Numeric(12, 2), nullable=False),
        sa.Column("descuento_linea", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("impuesto_tasa", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("producto_unidad_id", PGUUID(as_uuid=True), sa.ForeignKey("producto_unidad.id"), nullable=True),
        sa.Column("cantidad_en_unidad_base", sa.Numeric(14, 4), nullable=True),
        sa.Column("promo_id", PGUUID(as_uuid=True), sa.ForeignKey("promocion.id"), nullable=True),
        sa.Column("promo_etiqueta", sa.String(length=120), nullable=True),
        sa.Column("promo_descuento", sa.Numeric(12, 2), nullable=False, server_default="0"),
    )
    op.create_index("ix_detalle_pedido_pedido", "detalle_pedido", ["pedido_id"])

    op.create_table(
        "pedido_pago",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column("pedido_id", PGUUID(as_uuid=True), sa.ForeignKey("pedido.id", ondelete="CASCADE"), nullable=False),
        sa.Column("monto", sa.Numeric(12, 2), nullable=False),
        sa.Column("metodo_pago", sa.String(length=50), nullable=False),
        sa.Column("referencia", sa.String(length=120), nullable=True),
        sa.Column("reembolsado", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("monto > 0", name="ck_pedido_pago_monto_pos"),
    )
    op.alter_column("pedido_pago", "reembolsado", server_default=None)
    op.create_index("ix_pedido_pago_pedido", "pedido_pago", ["pedido_id"])

    bind = op.get_bind()
    for codigo, desc, roles in _PERMISOS:
        bind.execute(
            sa.text(
                "INSERT INTO permiso (id, codigo, descripcion) VALUES (:id, :c, :d) "
                "ON CONFLICT (codigo) DO NOTHING"
            ),
            {"id": str(uuid.uuid4()), "c": codigo, "d": desc},
        )
        for rol in roles:
            bind.execute(
                sa.text(
                    "INSERT INTO rol_permiso (rol_id, permiso_id) "
                    "SELECT r.id, p.id FROM rol r, permiso p "
                    "WHERE r.codigo = :rc AND p.codigo = :pc ON CONFLICT DO NOTHING"
                ),
                {"rc": rol, "pc": codigo},
            )


def downgrade() -> None:
    bind = op.get_bind()
    for codigo, _, _ in _PERMISOS:
        bind.execute(
            sa.text(
                "DELETE FROM rol_permiso WHERE permiso_id IN "
                "(SELECT id FROM permiso WHERE codigo = :c)"
            ),
            {"c": codigo},
        )
        bind.execute(sa.text("DELETE FROM permiso WHERE codigo = :c"), {"c": codigo})

    op.drop_index("ix_pedido_pago_pedido", table_name="pedido_pago")
    op.drop_table("pedido_pago")
    op.drop_index("ix_detalle_pedido_pedido", table_name="detalle_pedido")
    op.drop_table("detalle_pedido")
    for idx in (
        "ix_pedido_estado_entrega", "ix_pedido_repartidor", "ix_pedido_telefono",
        "ix_pedido_cliente", "ix_pedido_sucursal_estado",
    ):
        op.drop_index(idx, table_name="pedido")
    op.drop_table("pedido")
