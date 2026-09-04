"""producto_unidad (presentaciones de venta) + detalle_venta.producto_unidad_id

- Tabla `producto_unidad`: presentaciones adicionales de un producto
  ("Reja x24"), cada una con su `factor`, `precio_venta` y código de barras.
- `detalle_venta.producto_unidad_id`: qué presentación se vendió en cada línea
  (NULL = unidad base).

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-09-02 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c9d0e1f2a3b4"
down_revision: Union[str, Sequence[str], None] = "b8c9d0e1f2a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "producto_unidad",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("producto_id", sa.UUID(), nullable=False),
        sa.Column("nombre", sa.String(length=50), nullable=False),
        sa.Column("factor", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("precio_venta", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("codigo_barras", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["producto_id"], ["producto.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("factor > 0", name="ck_producto_unidad_factor_pos"),
    )
    op.create_index("ix_producto_unidad_producto", "producto_unidad", ["producto_id"])
    op.create_index(
        "uq_producto_unidad_nombre", "producto_unidad", ["producto_id", "nombre"],
        unique=True, postgresql_where=sa.text("activo"),
    )
    op.create_index(
        "uq_producto_unidad_codigo_barras", "producto_unidad", ["codigo_barras"],
        unique=True, postgresql_where=sa.text("activo"),
    )

    op.add_column(
        "detalle_venta",
        sa.Column("producto_unidad_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_detalle_venta_producto_unidad",
        "detalle_venta", "producto_unidad",
        ["producto_unidad_id"], ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_detalle_venta_producto_unidad", "detalle_venta", type_="foreignkey"
    )
    op.drop_column("detalle_venta", "producto_unidad_id")
    op.drop_index("uq_producto_unidad_codigo_barras", table_name="producto_unidad")
    op.drop_index("uq_producto_unidad_nombre", table_name="producto_unidad")
    op.drop_index("ix_producto_unidad_producto", table_name="producto_unidad")
    op.drop_table("producto_unidad")
