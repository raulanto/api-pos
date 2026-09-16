"""pedidos: servicios como lineas con responsable; quitar costo_envio

- `pedido.costo_envio` se elimina: el envío/servicio ahora es una línea normal
  con un producto de tipo `servicio` (nada de producto global por env var).
- `detalle_pedido` gana:
  - `es_servicio` (bool): lo congela el backend según el `tipo` del producto.
  - `asignado_a` (FK usuario): la persona responsable de ese servicio.
    Confirmar el pedido exige que toda línea `es_servicio` tenga `asignado_a`.

Revision ID: c0d1e2f3a4b5
Revises: a9b8c7d6e5f4
Create Date: 2026-09-09 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PGUUID


revision: str = "c0d1e2f3a4b5"
down_revision: Union[str, Sequence[str], None] = "a9b8c7d6e5f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("pedido", "costo_envio")

    op.add_column(
        "detalle_pedido",
        sa.Column("es_servicio", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.alter_column("detalle_pedido", "es_servicio", server_default=None)
    op.add_column(
        "detalle_pedido",
        sa.Column(
            "asignado_a", PGUUID(as_uuid=True), sa.ForeignKey("usuario.id"), nullable=True,
        ),
    )
    op.create_index(
        "ix_detalle_pedido_asignado", "detalle_pedido", ["asignado_a"],
    )


def downgrade() -> None:
    op.drop_index("ix_detalle_pedido_asignado", table_name="detalle_pedido")
    op.drop_column("detalle_pedido", "asignado_a")
    op.drop_column("detalle_pedido", "es_servicio")
    op.add_column(
        "pedido",
        sa.Column("costo_envio", sa.Numeric(12, 2), nullable=False, server_default="0"),
    )
    op.alter_column("pedido", "costo_envio", server_default=None)
