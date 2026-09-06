"""Instancia física abierta (envase destapado vendido en fracciones)

- `producto.rastrea_instancia_abierta` + `producto.instancia_capacidad_default`:
  activan el rastreo por producto y fijan la capacidad para auto-abrir al vender.
- `instancia_abierta`: un envase concreto con su saldo restante en unidad base.
- `movimiento_inventario.instancia_abierta_id`: de qué envase salió/entró la fracción.

Sin seed de permisos: reutiliza `inventario.movimiento` / `inventario.leer`.

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
Create Date: 2026-09-05 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PGUUID


revision: str = "d5e6f7a8b9c0"
down_revision: Union[str, Sequence[str], None] = "c4d5e6f7a8b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "producto",
        sa.Column(
            "rastrea_instancia_abierta", sa.Boolean(), nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "producto",
        sa.Column("instancia_capacidad_default", sa.Numeric(14, 4), nullable=True),
    )
    op.alter_column("producto", "rastrea_instancia_abierta", server_default=None)

    op.create_table(
        "instancia_abierta",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column(
            "producto_id", PGUUID(as_uuid=True),
            sa.ForeignKey("producto.id"), nullable=False,
        ),
        sa.Column(
            "sucursal_id", PGUUID(as_uuid=True),
            sa.ForeignKey("sucursal.id"), nullable=False,
        ),
        sa.Column(
            "producto_unidad_id", PGUUID(as_uuid=True),
            sa.ForeignKey("producto_unidad.id"), nullable=True,
        ),
        sa.Column(
            "lote_id", PGUUID(as_uuid=True), sa.ForeignKey("lote.id"), nullable=True,
        ),
        sa.Column("capacidad_inicial", sa.Numeric(14, 4), nullable=False),
        sa.Column("saldo", sa.Numeric(14, 4), nullable=False),
        sa.Column("estado", sa.String(length=12), nullable=False),
        sa.Column(
            "abierta_por", PGUUID(as_uuid=True),
            sa.ForeignKey("usuario.id"), nullable=False,
        ),
        sa.Column(
            "abierta_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("cerrada_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("motivo_cierre", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "capacidad_inicial > 0", name="ck_instancia_capacidad_positiva"
        ),
        sa.CheckConstraint(
            "saldo >= 0 AND saldo <= capacidad_inicial",
            name="ck_instancia_saldo_rango",
        ),
    )
    op.create_index(
        "ix_instancia_abierta_producto_sucursal", "instancia_abierta",
        ["producto_id", "sucursal_id"],
    )
    op.create_index(
        "ix_instancia_abierta_estado", "instancia_abierta", ["estado"],
    )
    op.create_index(
        "ix_instancia_abierta_lote", "instancia_abierta", ["lote_id"],
    )
    op.create_index(
        "ix_instancia_abierta_abiertas", "instancia_abierta",
        ["producto_id", "sucursal_id", "abierta_at"],
        postgresql_where=sa.text("estado = 'abierta'"),
    )

    op.add_column(
        "movimiento_inventario",
        sa.Column(
            "instancia_abierta_id", PGUUID(as_uuid=True),
            sa.ForeignKey("instancia_abierta.id"), nullable=True,
        ),
    )
    op.create_index(
        "ix_movimiento_instancia_abierta", "movimiento_inventario",
        ["instancia_abierta_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_movimiento_instancia_abierta", table_name="movimiento_inventario")
    op.drop_column("movimiento_inventario", "instancia_abierta_id")
    op.drop_index("ix_instancia_abierta_abiertas", table_name="instancia_abierta")
    op.drop_index("ix_instancia_abierta_lote", table_name="instancia_abierta")
    op.drop_index("ix_instancia_abierta_estado", table_name="instancia_abierta")
    op.drop_index(
        "ix_instancia_abierta_producto_sucursal", table_name="instancia_abierta"
    )
    op.drop_table("instancia_abierta")
    op.drop_column("producto", "instancia_capacidad_default")
    op.drop_column("producto", "rastrea_instancia_abierta")
