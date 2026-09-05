"""Trazabilidad de la unidad capturada

Fase 3 de "productos flexibles":
- `movimiento_inventario.unidad_capturada_id` (FK a producto_unidad) y
  `cantidad_capturada`: unidad y cantidad tal como se capturaron antes de
  convertir a unidad base.
- `detalle_venta.cantidad_en_unidad_base`: cantidad de la línea ya convertida a
  la unidad base del producto (se persiste para anulaciones y reportes).

Revision ID: e3c4d5e6f7a8
Revises: e2b3c4d5f6a7
Create Date: 2026-09-03 00:00:02.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PGUUID


revision: str = "e3c4d5e6f7a8"
down_revision: Union[str, Sequence[str], None] = "e2b3c4d5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "movimiento_inventario",
        sa.Column("unidad_capturada_id", PGUUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "movimiento_inventario",
        sa.Column("cantidad_capturada", sa.Numeric(14, 4), nullable=True),
    )
    op.create_foreign_key(
        "fk_movimiento_unidad_capturada", "movimiento_inventario", "producto_unidad",
        ["unidad_capturada_id"], ["id"],
    )

    op.add_column(
        "detalle_venta",
        sa.Column("cantidad_en_unidad_base", sa.Numeric(14, 4), nullable=True),
    )
    # Backfill: para líneas sin presentación (unidad base), la cantidad base = cantidad.
    op.execute(
        "UPDATE detalle_venta SET cantidad_en_unidad_base = cantidad "
        "WHERE cantidad_en_unidad_base IS NULL AND producto_unidad_id IS NULL"
    )


def downgrade() -> None:
    op.drop_column("detalle_venta", "cantidad_en_unidad_base")
    op.drop_constraint(
        "fk_movimiento_unidad_capturada", "movimiento_inventario", type_="foreignkey"
    )
    op.drop_column("movimiento_inventario", "cantidad_capturada")
    op.drop_column("movimiento_inventario", "unidad_capturada_id")
