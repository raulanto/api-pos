"""proveedores fase 2: pedido_proveedor

- Tablas `pedido_proveedor` + `pedido_proveedor_detalle` (orden de compra;
  `subtotal`/`total` se derivan de las líneas, no se persisten).
- Permisos `pedido_proveedor.leer/gestionar/generar_manual/confirmar_envio`.

Revision ID: 6726e66ed368
Revises: b3929c57dc09
Create Date: 2026-09-12 00:00:00.000001
"""
from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PGUUID


revision: str = '6726e66ed368'
down_revision: Union[str, Sequence[str], None] = 'b3929c57dc09'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_PERMISOS = [
    ("pedido_proveedor.leer", "Ver/listar pedidos a proveedor", ("admin", "gerente", "almacenista")),
    ("pedido_proveedor.gestionar", "Crear/editar en borrador/cancelar pedidos a proveedor",
     ("admin", "gerente", "almacenista")),
    ("pedido_proveedor.generar_manual", "Disparar el motor de reorden por stock mínimo",
     ("admin", "gerente", "almacenista")),
    ("pedido_proveedor.confirmar_envio", "Confirmar el envío de un pedido (borrador -> enviado)",
     ("admin", "gerente")),
]


def upgrade() -> None:
    op.create_table(
        "pedido_proveedor",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column("proveedor_id", PGUUID(as_uuid=True), sa.ForeignKey("proveedor.id"), nullable=False),
        sa.Column("sucursal_id", PGUUID(as_uuid=True), sa.ForeignKey("sucursal.id"), nullable=False),
        sa.Column("estado", sa.String(length=20), nullable=False),
        sa.Column("generado_automaticamente", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("generado_por", PGUUID(as_uuid=True), sa.ForeignKey("usuario.id"), nullable=True),
        sa.Column("confirmado_por", PGUUID(as_uuid=True), sa.ForeignKey("usuario.id"), nullable=True),
        sa.Column("fecha_pedido", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fecha_estimada_entrega", sa.Date(), nullable=True),
        sa.Column("notas", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "estado IN ('borrador', 'enviado', 'confirmado', 'parcial', 'recibido', 'cancelado')",
            name="ck_pedido_proveedor_estado",
        ),
    )
    op.alter_column("pedido_proveedor", "generado_automaticamente", server_default=None)
    op.create_index("ix_pedido_proveedor_proveedor", "pedido_proveedor", ["proveedor_id"])
    op.create_index("ix_pedido_proveedor_sucursal", "pedido_proveedor", ["sucursal_id"])

    op.create_table(
        "pedido_proveedor_detalle",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column(
            "pedido_id", PGUUID(as_uuid=True),
            sa.ForeignKey("pedido_proveedor.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("producto_id", PGUUID(as_uuid=True), sa.ForeignKey("producto.id"), nullable=False),
        sa.Column("cantidad_solicitada", sa.Numeric(14, 4), nullable=False),
        sa.Column("cantidad_recibida", sa.Numeric(14, 4), nullable=False, server_default="0"),
        sa.Column("precio_unitario", sa.Numeric(12, 2), nullable=False),
    )
    op.alter_column("pedido_proveedor_detalle", "cantidad_recibida", server_default=None)
    op.create_index("ix_pedido_proveedor_detalle_pedido", "pedido_proveedor_detalle", ["pedido_id"])

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

    op.drop_index("ix_pedido_proveedor_detalle_pedido", table_name="pedido_proveedor_detalle")
    op.drop_table("pedido_proveedor_detalle")
    op.drop_index("ix_pedido_proveedor_sucursal", table_name="pedido_proveedor")
    op.drop_index("ix_pedido_proveedor_proveedor", table_name="pedido_proveedor")
    op.drop_table("pedido_proveedor")
