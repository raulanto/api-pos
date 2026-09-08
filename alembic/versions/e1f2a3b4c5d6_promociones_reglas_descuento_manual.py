"""Promociones fase 1: reglas de aplicación + descuento manual auditado.

- `promocion`: `combinable`, `tope_descuento`, `monto_minimo_compra`.
- `detalle_venta_promo`: desglose congelado de promos apiladas por línea.
- `venta.motivo_descuento` (congela el motivo del descuento manual).
- `descuento_manual_limite` (tope de % por rol; NULL/sin fila = sin tope).
- Permiso `ventas.descuento_manual` (admin, gerente) + filas NULL para esos roles.

Revision ID: e1f2a3b4c5d6
Revises: d3e4f5a6b7c8
Create Date: 2026-09-08 00:00:00.000000
"""
import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PGUUID


revision: str = "e1f2a3b4c5d6"
down_revision: Union[str, Sequence[str], None] = "d3e4f5a6b7c8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_PERMISOS = [
    ("ventas.descuento_manual",
     "Aplicar descuento manual (por línea o total) en una venta",
     ("admin", "gerente")),
]


def upgrade() -> None:
    op.add_column(
        "promocion",
        sa.Column("combinable", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.alter_column("promocion", "combinable", server_default=None)
    op.add_column("promocion", sa.Column("tope_descuento", sa.Numeric(12, 2), nullable=True))
    op.add_column("promocion", sa.Column("monto_minimo_compra", sa.Numeric(12, 2), nullable=True))

    op.create_table(
        "detalle_venta_promo",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column(
            "detalle_venta_id", PGUUID(as_uuid=True),
            sa.ForeignKey("detalle_venta.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("promo_id", PGUUID(as_uuid=True), sa.ForeignKey("promocion.id"), nullable=True),
        sa.Column("promo_etiqueta", sa.String(length=120), nullable=True),
        sa.Column("monto", sa.Numeric(12, 2), nullable=False),
    )
    op.create_index(
        "ix_detalle_venta_promo_detalle", "detalle_venta_promo", ["detalle_venta_id"],
    )

    op.add_column("venta", sa.Column("motivo_descuento", sa.Text(), nullable=True))

    op.create_table(
        "descuento_manual_limite",
        sa.Column("rol_id", PGUUID(as_uuid=True), sa.ForeignKey("rol.id"), primary_key=True),
        sa.Column("pct_max", sa.Numeric(5, 2), nullable=True),
    )

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
    # admin / gerente: sin tope explícito (fila con pct_max NULL).
    bind.execute(
        sa.text(
            "INSERT INTO descuento_manual_limite (rol_id, pct_max) "
            "SELECT id, NULL FROM rol WHERE codigo IN ('admin', 'gerente') "
            "ON CONFLICT (rol_id) DO NOTHING"
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    for codigo, _desc, _roles in _PERMISOS:
        bind.execute(
            sa.text(
                "DELETE FROM rol_permiso WHERE permiso_id = "
                "(SELECT id FROM permiso WHERE codigo = :c)"
            ),
            {"c": codigo},
        )
        bind.execute(sa.text("DELETE FROM permiso WHERE codigo = :c"), {"c": codigo})

    op.drop_table("descuento_manual_limite")
    op.drop_column("venta", "motivo_descuento")
    op.drop_index("ix_detalle_venta_promo_detalle", table_name="detalle_venta_promo")
    op.drop_table("detalle_venta_promo")
    op.drop_column("promocion", "monto_minimo_compra")
    op.drop_column("promocion", "tope_descuento")
    op.drop_column("promocion", "combinable")
