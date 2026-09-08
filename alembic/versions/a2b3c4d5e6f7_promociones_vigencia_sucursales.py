"""Promociones fase 2: ventana horaria/días + alcance por lista de sucursales.

- `promocion`: `hora_desde`, `hora_hasta`, `dias_semana` (bitmask lun..dom).
- `promocion_sucursal` (lista); backfill desde `promocion.sucursal_id` y drop
  de la columna + su índice.

Revision ID: a2b3c4d5e6f7
Revises: e1f2a3b4c5d6
Create Date: 2026-09-08 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PGUUID


revision: str = "a2b3c4d5e6f7"
down_revision: Union[str, Sequence[str], None] = "e1f2a3b4c5d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("promocion", sa.Column("hora_desde", sa.Time(), nullable=True))
    op.add_column("promocion", sa.Column("hora_hasta", sa.Time(), nullable=True))
    op.add_column("promocion", sa.Column("dias_semana", sa.SmallInteger(), nullable=True))

    op.create_table(
        "promocion_sucursal",
        sa.Column(
            "promocion_id", PGUUID(as_uuid=True),
            sa.ForeignKey("promocion.id", ondelete="CASCADE"), primary_key=True,
        ),
        sa.Column(
            "sucursal_id", PGUUID(as_uuid=True),
            sa.ForeignKey("sucursal.id"), primary_key=True,
        ),
    )
    op.execute(
        "INSERT INTO promocion_sucursal (promocion_id, sucursal_id) "
        "SELECT id, sucursal_id FROM promocion WHERE sucursal_id IS NOT NULL"
    )
    op.drop_index("ix_promocion_sucursal", table_name="promocion")
    op.drop_column("promocion", "sucursal_id")


def downgrade() -> None:
    op.add_column(
        "promocion",
        sa.Column("sucursal_id", PGUUID(as_uuid=True), sa.ForeignKey("sucursal.id"), nullable=True),
    )
    op.execute(
        "UPDATE promocion p SET sucursal_id = ps.sucursal_id "
        "FROM promocion_sucursal ps WHERE ps.promocion_id = p.id"
    )
    op.create_index("ix_promocion_sucursal", "promocion", ["sucursal_id"])
    op.drop_table("promocion_sucursal")
    op.drop_column("promocion", "dias_semana")
    op.drop_column("promocion", "hora_hasta")
    op.drop_column("promocion", "hora_desde")
