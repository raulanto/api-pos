"""Galería de imágenes: producto_imagen

Catálogo de imágenes para productos (simples y kits) y para presentaciones de
venta (`producto_unidad`, p. ej. la unidad suelta de un producto fraccionable).
El dueño es EXACTAMENTE uno de los dos FK: `producto_id` XOR
`producto_unidad_id`. Es una galería (varias filas por dueño) con `orden` y
`es_principal` (portada/miniatura).

Revision ID: f2a3b4c5d6e7
Revises: e4d5e6f7a8b9
Create Date: 2026-09-04 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PGUUID


revision: str = "f2a3b4c5d6e7"
down_revision: Union[str, Sequence[str], None] = "e4d5e6f7a8b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "producto_imagen",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column(
            "producto_id", PGUUID(as_uuid=True),
            sa.ForeignKey("producto.id"), nullable=True,
        ),
        sa.Column(
            "producto_unidad_id", PGUUID(as_uuid=True),
            sa.ForeignKey("producto_unidad.id"), nullable=True,
        ),
        sa.Column("url", sa.String(length=500), nullable=False),
        sa.Column("alt_texto", sa.String(length=255), nullable=True),
        sa.Column("orden", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("es_principal", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "(producto_id IS NULL) <> (producto_unidad_id IS NULL)",
            name="ck_producto_imagen_un_solo_dueno",
        ),
    )
    op.alter_column("producto_imagen", "orden", server_default=None)
    op.alter_column("producto_imagen", "es_principal", server_default=None)
    op.create_index(
        "ix_producto_imagen_producto", "producto_imagen", ["producto_id"]
    )
    op.create_index(
        "ix_producto_imagen_producto_unidad", "producto_imagen", ["producto_unidad_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_producto_imagen_producto_unidad", table_name="producto_imagen")
    op.drop_index("ix_producto_imagen_producto", table_name="producto_imagen")
    op.drop_table("producto_imagen")
