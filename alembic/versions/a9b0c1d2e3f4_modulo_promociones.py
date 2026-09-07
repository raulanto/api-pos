"""Módulo promociones: tabla `promocion` + `promocion_objetivo`, columnas de
trazabilidad en `detalle_venta` y seed de permisos `promociones.*`.

- `promocion`: campaña de descuento (tipo nxm / porcentaje / precio_fijo),
  `prioridad`, `sucursal_id` opcional, ventana `vigente_desde/hasta`.
- `promocion_objetivo`: lista de productos / presentaciones a los que aplica.
- `detalle_venta`: `promo_id`, `promo_descuento` (NOT NULL, backfill 0),
  `promo_etiqueta`.
- Permisos `promociones.leer|crear|editar` para `admin` y `gerente`.

Revision ID: a9b0c1d2e3f4
Revises: f7a8b9c0d1e2
Create Date: 2026-09-07 00:00:00.000000
"""
from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PGUUID


revision: str = "a9b0c1d2e3f4"
down_revision: Union[str, Sequence[str], None] = "f7a8b9c0d1e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_PERMISOS = [
    ("promociones.leer", "Ver/listar promociones"),
    ("promociones.crear", "Crear promociones"),
    ("promociones.editar", "Editar/activar/desactivar promociones"),
]
_ROLES = ("admin", "gerente")


def upgrade() -> None:
    op.create_table(
        "promocion",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column("nombre", sa.String(length=120), nullable=False),
        sa.Column("tipo", sa.String(length=20), nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("prioridad", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("sucursal_id", PGUUID(as_uuid=True), sa.ForeignKey("sucursal.id"), nullable=True),
        sa.Column("vigente_desde", sa.DateTime(timezone=True), nullable=True),
        sa.Column("vigente_hasta", sa.DateTime(timezone=True), nullable=True),
        sa.Column("nxm_lleva", sa.Integer(), nullable=True),
        sa.Column("nxm_paga", sa.Integer(), nullable=True),
        sa.Column("descuento_pct", sa.Numeric(5, 2), nullable=True),
        sa.Column("precio_fijo", sa.Numeric(12, 2), nullable=True),
        sa.Column("cantidad_minima", sa.Numeric(14, 4), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("tipo IN ('nxm', 'porcentaje', 'precio_fijo')", name="ck_promocion_tipo"),
        sa.CheckConstraint("prioridad >= 0", name="ck_promocion_prioridad"),
        sa.UniqueConstraint("nombre", name="uq_promocion_nombre"),
    )
    op.alter_column("promocion", "activo", server_default=None)
    op.alter_column("promocion", "prioridad", server_default=None)
    op.create_index("ix_promocion_activo", "promocion", ["activo"])
    op.create_index("ix_promocion_sucursal", "promocion", ["sucursal_id"])

    op.create_table(
        "promocion_objetivo",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column(
            "promocion_id", PGUUID(as_uuid=True),
            sa.ForeignKey("promocion.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("producto_id", PGUUID(as_uuid=True), sa.ForeignKey("producto.id"), nullable=True),
        sa.Column(
            "producto_unidad_id", PGUUID(as_uuid=True),
            sa.ForeignKey("producto_unidad.id"), nullable=True,
        ),
        sa.CheckConstraint(
            "producto_id IS NOT NULL OR producto_unidad_id IS NOT NULL",
            name="ck_promocion_objetivo_target",
        ),
        sa.UniqueConstraint(
            "promocion_id", "producto_id", "producto_unidad_id", name="uq_promocion_objetivo",
        ),
    )
    op.create_index("ix_promocion_objetivo_promocion", "promocion_objetivo", ["promocion_id"])

    op.add_column("detalle_venta", sa.Column("promo_id", PGUUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_detalle_venta_promo", "detalle_venta", "promocion", ["promo_id"], ["id"],
    )
    op.add_column(
        "detalle_venta",
        sa.Column("promo_descuento", sa.Numeric(12, 2), nullable=False, server_default="0"),
    )
    op.alter_column("detalle_venta", "promo_descuento", server_default=None)
    op.add_column("detalle_venta", sa.Column("promo_etiqueta", sa.String(length=120), nullable=True))

    bind = op.get_bind()
    for codigo, desc in _PERMISOS:
        bind.execute(
            sa.text(
                "INSERT INTO permiso (id, codigo, descripcion) VALUES (:id, :c, :d) "
                "ON CONFLICT (codigo) DO NOTHING"
            ),
            {"id": str(uuid.uuid4()), "c": codigo, "d": desc},
        )
        for rol in _ROLES:
            bind.execute(
                sa.text(
                    "INSERT INTO rol_permiso (rol_id, permiso_id) "
                    "SELECT r.id, p.id FROM rol r, permiso p "
                    "WHERE r.codigo = :rc AND p.codigo = :pc "
                    "ON CONFLICT DO NOTHING"
                ),
                {"rc": rol, "pc": codigo},
            )


def downgrade() -> None:
    bind = op.get_bind()
    for codigo, _ in _PERMISOS:
        bind.execute(
            sa.text(
                "DELETE FROM rol_permiso WHERE permiso_id IN "
                "(SELECT id FROM permiso WHERE codigo = :c)"
            ),
            {"c": codigo},
        )
        bind.execute(sa.text("DELETE FROM permiso WHERE codigo = :c"), {"c": codigo})

    op.drop_constraint("fk_detalle_venta_promo", "detalle_venta", type_="foreignkey")
    op.drop_column("detalle_venta", "promo_etiqueta")
    op.drop_column("detalle_venta", "promo_descuento")
    op.drop_column("detalle_venta", "promo_id")

    op.drop_index("ix_promocion_objetivo_promocion", table_name="promocion_objetivo")
    op.drop_table("promocion_objetivo")
    op.drop_index("ix_promocion_sucursal", table_name="promocion")
    op.drop_index("ix_promocion_activo", table_name="promocion")
    op.drop_table("promocion")
