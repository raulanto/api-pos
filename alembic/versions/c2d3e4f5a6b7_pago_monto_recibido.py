"""Pago: `monto_recibido` (efectivo con el que pagó el cliente, para el cambio).

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2026-09-07 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c2d3e4f5a6b7"
down_revision: Union[str, Sequence[str], None] = "b1c2d3e4f5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("pago", sa.Column("monto_recibido", sa.Numeric(12, 2), nullable=True))


def downgrade() -> None:
    op.drop_column("pago", "monto_recibido")
