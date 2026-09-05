"""Catálogo `unidad_medida` + FK desde producto y producto_unidad

Fase 1 de "productos flexibles":
- Nueva tabla `unidad_medida` (código único, tipo de magnitud, decimales) con
  un seed base.
- `producto.unidad_medida_id` y `producto_unidad.unidad_medida_id` (FK nullable).
  Se mantiene la columna de texto `unidad_medida` como fallback; se hace un
  backfill best-effort haciendo match del texto contra `codigo` o `nombre`.

Revision ID: e1a2b3c4d5f6
Revises: d0e1f2a3b4c5
Create Date: 2026-09-03 00:00:00.000000
"""
from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PGUUID


revision: str = "e1a2b3c4d5f6"
down_revision: Union[str, Sequence[str], None] = "d0e1f2a3b4c5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (codigo, nombre, tipo_magnitud, decimales)
_SEED: list[tuple[str, str, str, int]] = [
    ("unidad", "Unidad", "conteo", 0),
    ("pza", "Pieza", "conteo", 0),
    ("caja", "Caja", "conteo", 0),
    ("paquete", "Paquete", "conteo", 0),
    ("reja", "Reja", "conteo", 0),
    ("docena", "Docena", "conteo", 0),
    ("kg", "Kilogramo", "masa", 3),
    ("g", "Gramo", "masa", 0),
    ("l", "Litro", "volumen", 3),
    ("ml", "Mililitro", "volumen", 0),
    ("m", "Metro", "longitud", 2),
    ("cm", "Centímetro", "longitud", 0),
    ("hora", "Hora", "tiempo", 2),
    ("dia", "Día", "tiempo", 0),
]


def upgrade() -> None:
    op.create_table(
        "unidad_medida",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column("codigo", sa.String(length=20), nullable=False),
        sa.Column("nombre", sa.String(length=60), nullable=False),
        sa.Column("tipo_magnitud", sa.String(length=20), nullable=False),
        sa.Column("decimales", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "decimales >= 0 AND decimales <= 6", name="ck_unidad_medida_decimales"
        ),
    )
    op.create_index(
        "uq_unidad_medida_codigo", "unidad_medida", ["codigo"], unique=True
    )
    op.alter_column("unidad_medida", "decimales", server_default=None)

    bind = op.get_bind()
    for codigo, nombre, magnitud, decimales in _SEED:
        bind.execute(
            sa.text(
                "INSERT INTO unidad_medida (id, codigo, nombre, tipo_magnitud, decimales) "
                "VALUES (:id, :c, :n, :m, :d) ON CONFLICT (codigo) DO NOTHING"
            ),
            {"id": str(uuid.uuid4()), "c": codigo, "n": nombre, "m": magnitud, "d": decimales},
        )

    # --- FK desde producto ---
    op.add_column(
        "producto",
        sa.Column("unidad_medida_id", PGUUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_producto_unidad_medida", "producto", "unidad_medida",
        ["unidad_medida_id"], ["id"],
    )
    op.create_index(
        "ix_producto_unidad_medida_id", "producto", ["unidad_medida_id"]
    )

    # --- FK desde producto_unidad (presentaciones) ---
    op.add_column(
        "producto_unidad",
        sa.Column("unidad_medida_id", PGUUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_producto_unidad_unidad_medida", "producto_unidad", "unidad_medida",
        ["unidad_medida_id"], ["id"],
    )
    op.create_index(
        "ix_producto_unidad_unidad_medida_id", "producto_unidad", ["unidad_medida_id"]
    )

    # --- Backfill best-effort por texto (codigo o nombre, sin distinguir mayúsculas) ---
    for tabla in ("producto", "producto_unidad"):
        bind.execute(sa.text(
            f"UPDATE {tabla} t SET unidad_medida_id = u.id "
            "FROM unidad_medida u "
            "WHERE t.unidad_medida_id IS NULL "
            "AND lower(btrim(t.unidad_medida)) IN (lower(u.codigo), lower(u.nombre))"
        ))


def downgrade() -> None:
    op.drop_index("ix_producto_unidad_unidad_medida_id", table_name="producto_unidad")
    op.drop_constraint(
        "fk_producto_unidad_unidad_medida", "producto_unidad", type_="foreignkey"
    )
    op.drop_column("producto_unidad", "unidad_medida_id")

    op.drop_index("ix_producto_unidad_medida_id", table_name="producto")
    op.drop_constraint("fk_producto_unidad_medida", "producto", type_="foreignkey")
    op.drop_column("producto", "unidad_medida_id")

    op.drop_index("uq_unidad_medida_codigo", table_name="unidad_medida")
    op.drop_table("unidad_medida")
