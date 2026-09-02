"""Existencia: una sola fila de saldo por (producto, sucursal)

El stock de un producto se lleva por sucursal (tabla `existencia`), pero nada
garantizaba que hubiera a lo sumo una fila por par (producto_id, sucursal_id).
Esta migración:

1. Colapsa cualquier duplicado preexistente en una sola fila (suma `cantidad`,
   conserva el umbral mayor) para poder crear la restricción sin fallar.
2. Crea la restricción única `uq_existencia_producto_sucursal`, que es la clave
   natural que asumen `obtener`, `actualizar_cantidad` y `actualizar_umbrales`.
3. Crea `ix_existencia_sucursal_id` para los listados filtrados por sucursal.

Revision ID: f1a2b3c4d5e6
Revises: 8c8a659b98e9
Create Date: 2026-09-01 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, Sequence[str], None] = "8c8a659b98e9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_DEDUPE = """
WITH ganador AS (
    SELECT DISTINCT ON (producto_id, sucursal_id) id, producto_id, sucursal_id
    FROM existencia
    ORDER BY producto_id, sucursal_id, updated_at ASC, ctid ASC
),
agregado AS (
    SELECT producto_id,
           sucursal_id,
           SUM(cantidad)      AS cantidad,
           MAX(stock_minimo)  AS stock_minimo,
           MAX(stock_maximo)  AS stock_maximo
    FROM existencia
    GROUP BY producto_id, sucursal_id
),
_upd AS (
    UPDATE existencia e
    SET cantidad     = a.cantidad,
        stock_minimo = a.stock_minimo,
        stock_maximo = a.stock_maximo
    FROM ganador g
    JOIN agregado a
      ON a.producto_id = g.producto_id AND a.sucursal_id = g.sucursal_id
    WHERE e.id = g.id
    RETURNING 1
)
DELETE FROM existencia e
USING ganador g
WHERE e.producto_id = g.producto_id
  AND e.sucursal_id = g.sucursal_id
  AND e.id <> g.id;
"""


def upgrade() -> None:
    op.execute(_DEDUPE)
    op.create_unique_constraint(
        "uq_existencia_producto_sucursal", "existencia", ["producto_id", "sucursal_id"]
    )
    op.create_index("ix_existencia_sucursal_id", "existencia", ["sucursal_id"])


def downgrade() -> None:
    op.drop_index("ix_existencia_sucursal_id", table_name="existencia")
    op.drop_constraint(
        "uq_existencia_producto_sucursal", "existencia", type_="unique"
    )
