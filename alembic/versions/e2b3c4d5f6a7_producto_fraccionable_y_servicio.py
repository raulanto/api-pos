"""producto: venta fraccionada (permite_venta_fraccionada, incremento_minimo_venta)

Fase 2 de "productos flexibles". El enum `TipoProducto` gana los valores
`fraccionable` y `servicio`, pero `producto.tipo` ya es VARCHAR(20): no hay
cambio de esquema por eso. Sólo se agregan dos columnas de reglas de venta.

Revision ID: e2b3c4d5f6a7
Revises: e1a2b3c4d5f6
Create Date: 2026-09-03 00:00:01.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e2b3c4d5f6a7"
down_revision: Union[str, Sequence[str], None] = "e1a2b3c4d5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "producto",
        sa.Column(
            "permite_venta_fraccionada", sa.Boolean(), nullable=False,
            server_default=sa.false(),
        ),
    )
    op.alter_column("producto", "permite_venta_fraccionada", server_default=None)
    op.add_column(
        "producto",
        sa.Column("incremento_minimo_venta", sa.Numeric(14, 4), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("producto", "incremento_minimo_venta")
    op.drop_column("producto", "permite_venta_fraccionada")
