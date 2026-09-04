"""producto_unidad.unidad_medida + factor con más precisión

- `producto_unidad.unidad_medida`: cada presentación tiene su propia unidad de
  medida ("pieza", "litro"), distinta de la del producto padre ("reja").
- `factor` pasa a NUMERIC(12,6) para admitir fracciones (1/6, 1/12...).

(El costo/precio actualizable desde un movimiento no toca el esquema: son campos
del request de `POST /movimientos`.)

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
Create Date: 2026-09-02 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d0e1f2a3b4c5"
down_revision: Union[str, Sequence[str], None] = "c9d0e1f2a3b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "producto_unidad",
        sa.Column("unidad_medida", sa.String(length=20), nullable=False,
                  server_default="unidad"),
    )
    op.alter_column("producto_unidad", "unidad_medida", server_default=None)
    op.alter_column(
        "producto_unidad", "factor",
        type_=sa.Numeric(precision=12, scale=6),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "producto_unidad", "factor",
        type_=sa.Numeric(precision=12, scale=4),
        existing_nullable=False,
    )
    op.drop_column("producto_unidad", "unidad_medida")
