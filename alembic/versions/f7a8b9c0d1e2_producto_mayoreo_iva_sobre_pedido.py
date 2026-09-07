"""producto: mayoreo, precio con IVA incluido y sobre pedido

- `precio_incluye_impuesto` (bool): `precio_venta` ya trae el IVA adentro.
- `precio_mayoreo` + `cantidad_minima_mayoreo`: precio alternativo a partir de N
  unidades base; el backend lo aplica solo en la venta.
- `es_sobre_pedido` (bool): no se mantiene en stock, se vende sin existencia.

Revision ID: f7a8b9c0d1e2
Revises: e6f7a8b9c0d1
Create Date: 2026-09-06 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f7a8b9c0d1e2"
down_revision: Union[str, Sequence[str], None] = "e6f7a8b9c0d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for col in ("precio_incluye_impuesto", "es_sobre_pedido"):
        op.add_column(
            "producto",
            sa.Column(col, sa.Boolean(), nullable=False, server_default=sa.false()),
        )
        op.alter_column("producto", col, server_default=None)
    op.add_column("producto", sa.Column("precio_mayoreo", sa.Numeric(12, 2), nullable=True))
    op.add_column(
        "producto", sa.Column("cantidad_minima_mayoreo", sa.Numeric(14, 4), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("producto", "cantidad_minima_mayoreo")
    op.drop_column("producto", "precio_mayoreo")
    op.drop_column("producto", "es_sobre_pedido")
    op.drop_column("producto", "precio_incluye_impuesto")
