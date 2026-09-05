"""Ampliar precisión de las cantidades a NUMERIC(14,4)

Decisión previa a "productos flexibles": con venta fraccionada por presentación
(vender 5/6 de una reja) 2 decimales pierden información. Se amplían las
columnas de *cantidad* (no las de dinero) a NUMERIC(14,4).

- existencia.cantidad / stock_minimo / stock_maximo
- movimiento_inventario.cantidad
- detalle_venta.cantidad

Revision ID: e4d5e6f7a8b9
Revises: e3c4d5e6f7a8
Create Date: 2026-09-03 00:00:03.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e4d5e6f7a8b9"
down_revision: Union[str, Sequence[str], None] = "e3c4d5e6f7a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ANCHO = sa.Numeric(14, 4)
_VIEJO = sa.Numeric(12, 2)

_COLUMNAS = [
    ("existencia", "cantidad", False),
    ("existencia", "stock_minimo", False),
    ("existencia", "stock_maximo", True),
    ("movimiento_inventario", "cantidad", False),
    ("detalle_venta", "cantidad", False),
]


def upgrade() -> None:
    for tabla, col, nullable in _COLUMNAS:
        op.alter_column(
            tabla, col, type_=_ANCHO, existing_type=_VIEJO, existing_nullable=nullable
        )


def downgrade() -> None:
    for tabla, col, nullable in _COLUMNAS:
        op.alter_column(
            tabla, col, type_=_VIEJO, existing_type=_ANCHO, existing_nullable=nullable
        )
