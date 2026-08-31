"""SKU y código de barras únicos sólo entre productos activos

Reemplaza las restricciones UNIQUE globales de `producto.sku` y
`producto.codigo_barras` por índices únicos parciales (WHERE activo), para que
un producto dado de baja libere su SKU/código de barras.

Revision ID: c1d2e3f4a5b6
Revises: 6308ef5d63b3
Create Date: 2026-08-30 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c1d2e3f4a5b6"
down_revision: Union[str, Sequence[str], None] = "6308ef5d63b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Los nombres por defecto de PostgreSQL para UniqueConstraint('col') son
    # "<tabla>_<col>_key". Usamos IF EXISTS por robustez.
    op.execute("ALTER TABLE producto DROP CONSTRAINT IF EXISTS producto_sku_key")
    op.execute("ALTER TABLE producto DROP CONSTRAINT IF EXISTS producto_codigo_barras_key")

    op.create_index(
        "uq_producto_sku_activo", "producto", ["sku"],
        unique=True, postgresql_where=sa.text("activo"),
    )
    op.create_index(
        "uq_producto_codigo_barras_activo", "producto", ["codigo_barras"],
        unique=True, postgresql_where=sa.text("activo"),
    )


def downgrade() -> None:
    op.drop_index("uq_producto_codigo_barras_activo", table_name="producto")
    op.drop_index("uq_producto_sku_activo", table_name="producto")
    op.create_unique_constraint("producto_sku_key", "producto", ["sku"])
    op.create_unique_constraint("producto_codigo_barras_key", "producto", ["codigo_barras"])
