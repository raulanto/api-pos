"""ventas: detalle_venta.cita_id

Vínculo trazable (desacoplado) entre una línea de venta y la cita de `agenda`
que factura: `ventas` sólo guarda el id, no conoce el modelo de `agenda`.

Revision ID: 3fa9b0f7d846
Revises: 642e7dd5ecb1
Create Date: 2026-09-11 12:53:28.131276
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PGUUID


revision: str = '3fa9b0f7d846'
down_revision: Union[str, Sequence[str], None] = '642e7dd5ecb1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "detalle_venta",
        sa.Column("cita_id", PGUUID(as_uuid=True), sa.ForeignKey("cita.id"), nullable=True),
    )
    op.create_index("ix_detalle_venta_cita", "detalle_venta", ["cita_id"])


def downgrade() -> None:
    op.drop_index("ix_detalle_venta_cita", table_name="detalle_venta")
    op.drop_column("detalle_venta", "cita_id")
