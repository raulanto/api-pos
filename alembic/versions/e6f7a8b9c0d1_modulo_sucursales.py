"""Módulo sucursales: campos de ficha, jerarquía y fachada

`sucursal` deja de ser un catálogo pasivo. Solo ALTER (la tabla no se recrea,
las FK `-> sucursal.id` de usuario/existencia/venta/… quedan intactas):

- `codigo` VARCHAR(20) nullable + índice UNIQUE (Postgres admite varios NULL).
- `tipo` VARCHAR(20) NOT NULL (backfill 'tienda') + CHECK del enum.
- ficha: `descripcion`, `colonia`, `ciudad`, `estado`, `codigo_postal`, `pais`,
  `latitud`, `longitud`, `email`, `horario_apertura`, `horario_cierre` — nullable.
- `imagen_fachada_key` VARCHAR(500) nullable (key en el bucket, no la URL).
- `sucursal_padre_id` UUID nullable, self-FK + índice (jerarquía).
- `permite_ventas` BOOLEAN NOT NULL (backfill true).

Sin seed de permisos: `sucursales.*` ya existen.

Revision ID: e6f7a8b9c0d1
Revises: d5e6f7a8b9c0
Create Date: 2026-09-05 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PGUUID


revision: str = "e6f7a8b9c0d1"
down_revision: Union[str, Sequence[str], None] = "d5e6f7a8b9c0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NULLABLE = [
    ("descripcion", sa.Text()),
    ("imagen_fachada_key", sa.String(length=500)),
    ("colonia", sa.String(length=100)),
    ("ciudad", sa.String(length=100)),
    ("estado", sa.String(length=100)),
    ("codigo_postal", sa.String(length=10)),
    ("pais", sa.String(length=60)),
    ("latitud", sa.Numeric(10, 7)),
    ("longitud", sa.Numeric(10, 7)),
    ("email", sa.String(length=150)),
    ("horario_apertura", sa.Time()),
    ("horario_cierre", sa.Time()),
]


def upgrade() -> None:
    op.add_column("sucursal", sa.Column("codigo", sa.String(length=20), nullable=True))
    op.create_index("uq_sucursal_codigo", "sucursal", ["codigo"], unique=True)

    op.add_column(
        "sucursal",
        sa.Column("tipo", sa.String(length=20), nullable=False, server_default="tienda"),
    )
    op.alter_column("sucursal", "tipo", server_default=None)
    op.create_check_constraint(
        "ck_sucursal_tipo", "sucursal",
        "tipo IN ('bodega_central', 'tienda', 'almacen', 'cedis', 'oficina')",
    )

    for nombre, tipo in _NULLABLE:
        op.add_column("sucursal", sa.Column(nombre, tipo, nullable=True))

    op.add_column(
        "sucursal",
        sa.Column(
            "sucursal_padre_id", PGUUID(as_uuid=True),
            sa.ForeignKey("sucursal.id"), nullable=True,
        ),
    )
    op.create_index("ix_sucursal_padre", "sucursal", ["sucursal_padre_id"])

    op.add_column(
        "sucursal",
        sa.Column(
            "permite_ventas", sa.Boolean(), nullable=False, server_default=sa.true()
        ),
    )
    op.alter_column("sucursal", "permite_ventas", server_default=None)


def downgrade() -> None:
    op.drop_column("sucursal", "permite_ventas")
    op.drop_index("ix_sucursal_padre", table_name="sucursal")
    op.drop_column("sucursal", "sucursal_padre_id")
    for nombre, _ in _NULLABLE:
        op.drop_column("sucursal", nombre)
    op.drop_constraint("ck_sucursal_tipo", "sucursal", type_="check")
    op.drop_column("sucursal", "tipo")
    op.drop_index("uq_sucursal_codigo", table_name="sucursal")
    op.drop_column("sucursal", "codigo")
