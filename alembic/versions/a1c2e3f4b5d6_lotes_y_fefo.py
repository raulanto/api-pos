"""Control por lote y FEFO

- `lote`: catálogo de lotes por producto (código, caducidad, costo, proveedor).
- `existencia_lote`: saldo por (sucursal, lote); el desglose de `existencia`.
- `producto.requiere_lote`: activa el control por lote (ENTRADA con lote, SALIDA
  por FEFO).
- `movimiento_inventario.lote_id`: lote afectado por el movimiento.

Revision ID: a1c2e3f4b5d6
Revises: f2a3b4c5d6e7
Create Date: 2026-09-05 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PGUUID


revision: str = "a1c2e3f4b5d6"
down_revision: Union[str, Sequence[str], None] = "f2a3b4c5d6e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "lote",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column(
            "producto_id", PGUUID(as_uuid=True),
            sa.ForeignKey("producto.id"), nullable=False,
        ),
        sa.Column("codigo_lote", sa.String(length=60), nullable=False),
        sa.Column("fecha_caducidad", sa.Date(), nullable=True),
        sa.Column("costo", sa.Numeric(12, 2), nullable=False),
        sa.Column("proveedor", sa.String(length=150), nullable=True),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint("costo >= 0", name="ck_lote_costo_no_negativo"),
    )
    op.create_index(
        "uq_lote_producto_codigo_activo", "lote", ["producto_id", "codigo_lote"],
        unique=True, postgresql_where=sa.text("activo"),
    )
    op.create_index("ix_lote_producto", "lote", ["producto_id"])
    op.create_index("ix_lote_caducidad", "lote", ["fecha_caducidad"])
    op.alter_column("lote", "activo", server_default=None)

    op.create_table(
        "existencia_lote",
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
            "lote_id", PGUUID(as_uuid=True),
            sa.ForeignKey("lote.id"), nullable=False,
        ),
        sa.Column("cantidad", sa.Numeric(14, 4), nullable=False, server_default="0"),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "sucursal_id", "lote_id", name="uq_existencia_lote_sucursal_lote"
        ),
    )
    op.create_index(
        "ix_existencia_lote_prod_suc", "existencia_lote", ["producto_id", "sucursal_id"]
    )
    op.alter_column("existencia_lote", "cantidad", server_default=None)

    op.add_column(
        "producto",
        sa.Column(
            "requiere_lote", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )
    op.alter_column("producto", "requiere_lote", server_default=None)

    op.add_column(
        "movimiento_inventario",
        sa.Column("lote_id", PGUUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_movimiento_lote", "movimiento_inventario", "lote", ["lote_id"], ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_movimiento_lote", "movimiento_inventario", type_="foreignkey")
    op.drop_column("movimiento_inventario", "lote_id")
    op.drop_column("producto", "requiere_lote")
    op.drop_index("ix_existencia_lote_prod_suc", table_name="existencia_lote")
    op.drop_table("existencia_lote")
    op.drop_index("ix_lote_caducidad", table_name="lote")
    op.drop_index("ix_lote_producto", table_name="lote")
    op.drop_index("uq_lote_producto_codigo_activo", table_name="lote")
    op.drop_table("lote")
