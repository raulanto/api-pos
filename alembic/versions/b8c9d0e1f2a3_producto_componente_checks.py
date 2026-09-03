"""producto_componente: checks de integridad + índice

- ck_producto_componente_cantidad_pos: cantidad > 0
- ck_producto_componente_distinto: un producto no puede ser componente de sí mismo
- ix_producto_componente_componente: índice sobre producto_componente_id

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-09-02 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op


revision: str = "b8c9d0e1f2a3"
down_revision: Union[str, Sequence[str], None] = "a7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Limpia filas inconsistentes preexistentes antes de crear los checks.
    op.execute(
        "DELETE FROM producto_componente "
        "WHERE cantidad <= 0 OR producto_kit_id = producto_componente_id"
    )
    op.create_check_constraint(
        "ck_producto_componente_cantidad_pos", "producto_componente", "cantidad > 0"
    )
    op.create_check_constraint(
        "ck_producto_componente_distinto",
        "producto_componente",
        "producto_kit_id <> producto_componente_id",
    )
    op.create_index(
        "ix_producto_componente_componente",
        "producto_componente",
        ["producto_componente_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_producto_componente_componente", table_name="producto_componente")
    op.drop_constraint(
        "ck_producto_componente_distinto", "producto_componente", type_="check"
    )
    op.drop_constraint(
        "ck_producto_componente_cantidad_pos", "producto_componente", type_="check"
    )
