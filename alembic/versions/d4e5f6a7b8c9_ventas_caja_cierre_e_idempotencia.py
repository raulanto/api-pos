"""Ventas: cierre de turno de caja e idempotencia de venta

- caja_turno: saldo_final_declarado, diferencia (se llenan al cerrar el turno)
- venta: idempotency_key (única) para deduplicar POST /ventas reintentado

Revision ID: d4e5f6a7b8c9
Revises: 93cbcf273eae
Create Date: 2026-08-31 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, Sequence[str], None] = "93cbcf273eae"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("caja_turno", sa.Column("saldo_final_declarado", sa.Numeric(12, 2), nullable=True))
    op.add_column("caja_turno", sa.Column("diferencia", sa.Numeric(12, 2), nullable=True))
    op.add_column("venta", sa.Column("idempotency_key", sa.String(length=80), nullable=True))
    op.create_unique_constraint("uq_venta_idempotency_key", "venta", ["idempotency_key"])


def downgrade() -> None:
    op.drop_constraint("uq_venta_idempotency_key", "venta", type_="unique")
    op.drop_column("venta", "idempotency_key")
    op.drop_column("caja_turno", "diferencia")
    op.drop_column("caja_turno", "saldo_final_declarado")
