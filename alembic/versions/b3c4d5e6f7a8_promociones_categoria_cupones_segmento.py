"""Promociones fase 3: objetivo por categoría, cupones, condición por método de
pago y por segmento de cliente.

- `promocion`: `metodo_pago_requerido`, `cliente_segmento`, `requiere_cupon`.
- `promocion_objetivo`: `categoria_id` (+ CHECK y UNIQUE de 3 vías).
- `cliente.segmento`.
- `cupon` + `cupon_uso`.

Revision ID: b3c4d5e6f7a8
Revises: a2b3c4d5e6f7
Create Date: 2026-09-08 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PGUUID


revision: str = "b3c4d5e6f7a8"
down_revision: Union[str, Sequence[str], None] = "a2b3c4d5e6f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_CHECK_3 = (
    "(producto_id IS NOT NULL)::int + (producto_unidad_id IS NOT NULL)::int "
    "+ (categoria_id IS NOT NULL)::int = 1"
)
_CHECK_2 = "producto_id IS NOT NULL OR producto_unidad_id IS NOT NULL"


def upgrade() -> None:
    op.add_column("promocion", sa.Column("metodo_pago_requerido", sa.String(20), nullable=True))
    op.add_column("promocion", sa.Column("cliente_segmento", sa.String(30), nullable=True))
    op.add_column(
        "promocion",
        sa.Column("requiere_cupon", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.alter_column("promocion", "requiere_cupon", server_default=None)

    op.add_column(
        "promocion_objetivo",
        sa.Column("categoria_id", PGUUID(as_uuid=True), sa.ForeignKey("categoria.id"), nullable=True),
    )
    op.drop_constraint("ck_promocion_objetivo_target", "promocion_objetivo", type_="check")
    op.create_check_constraint("ck_promocion_objetivo_target", "promocion_objetivo", _CHECK_3)
    op.drop_constraint("uq_promocion_objetivo", "promocion_objetivo", type_="unique")
    op.create_unique_constraint(
        "uq_promocion_objetivo", "promocion_objetivo",
        ["promocion_id", "producto_id", "producto_unidad_id", "categoria_id"],
    )

    op.add_column("cliente", sa.Column("segmento", sa.String(30), nullable=True))

    op.create_table(
        "cupon",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column("codigo", sa.String(40), nullable=False, unique=True),
        sa.Column(
            "promocion_id", PGUUID(as_uuid=True),
            sa.ForeignKey("promocion.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("vigente_desde", sa.DateTime(timezone=True), nullable=True),
        sa.Column("vigente_hasta", sa.DateTime(timezone=True), nullable=True),
        sa.Column("max_usos_total", sa.Integer(), nullable=True),
        sa.Column("max_usos_por_persona", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_cupon_promocion", "cupon", ["promocion_id"])

    op.create_table(
        "cupon_uso",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column("cupon_id", PGUUID(as_uuid=True), sa.ForeignKey("cupon.id", ondelete="CASCADE"), nullable=False),
        sa.Column("venta_id", PGUUID(as_uuid=True), sa.ForeignKey("venta.id"), nullable=False),
        sa.Column("telefono", sa.String(50), nullable=True),
        sa.Column("cliente_id", PGUUID(as_uuid=True), nullable=True),
        sa.Column("monto_descontado", sa.Numeric(12, 2), nullable=False),
        sa.Column("usado_en", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_cupon_uso_cupon", "cupon_uso", ["cupon_id"])
    op.create_index("ix_cupon_uso_cupon_tel", "cupon_uso", ["cupon_id", "telefono"])
    op.create_index("ix_cupon_uso_cupon_cli", "cupon_uso", ["cupon_id", "cliente_id"])
    op.create_index("ix_cupon_uso_venta", "cupon_uso", ["venta_id"])


def downgrade() -> None:
    op.drop_table("cupon_uso")
    op.drop_index("ix_cupon_promocion", table_name="cupon")
    op.drop_table("cupon")
    op.drop_column("cliente", "segmento")

    op.drop_constraint("uq_promocion_objetivo", "promocion_objetivo", type_="unique")
    op.create_unique_constraint(
        "uq_promocion_objetivo", "promocion_objetivo",
        ["promocion_id", "producto_id", "producto_unidad_id"],
    )
    op.drop_constraint("ck_promocion_objetivo_target", "promocion_objetivo", type_="check")
    op.create_check_constraint("ck_promocion_objetivo_target", "promocion_objetivo", _CHECK_2)
    op.drop_column("promocion_objetivo", "categoria_id")

    op.drop_column("promocion", "requiere_cupon")
    op.drop_column("promocion", "cliente_segmento")
    op.drop_column("promocion", "metodo_pago_requerido")
