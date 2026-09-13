"""proveedores fase 1: proveedor y producto_proveedor

- Tabla `proveedor` (código único entre proveedores activos, igual que
  `producto.sku`).
- Tabla `producto_proveedor` (vínculo N:N producto-proveedor; un solo
  principal activo por producto vía índice único parcial).
- Permisos `proveedores.leer/crear/editar`, `producto_proveedor.gestionar`.

Revision ID: b3929c57dc09
Revises: 3fa9b0f7d846
Create Date: 2026-09-12 00:00:00.000000
"""
from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PGUUID


revision: str = 'b3929c57dc09'
down_revision: Union[str, Sequence[str], None] = '3fa9b0f7d846'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_PERMISOS = [
    ("proveedores.leer", "Ver/listar proveedores", ("admin", "gerente", "almacenista")),
    ("proveedores.crear", "Dar de alta proveedores", ("admin", "gerente")),
    ("proveedores.editar", "Editar/desactivar proveedores", ("admin", "gerente")),
    ("producto_proveedor.gestionar", "Vincular productos a proveedores, marcar principal",
     ("admin", "gerente", "almacenista")),
]


def upgrade() -> None:
    op.create_table(
        "proveedor",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column("codigo", sa.String(length=30), nullable=False),
        sa.Column("razon_social", sa.String(length=200), nullable=False),
        sa.Column("nombre_comercial", sa.String(length=200), nullable=True),
        sa.Column("rfc", sa.String(length=20), nullable=True),
        sa.Column("tipo_persona", sa.String(length=10), nullable=False),
        sa.Column("condiciones_pago", sa.String(length=10), nullable=False),
        sa.Column("dias_credito", sa.Integer(), nullable=True),
        sa.Column("moneda", sa.String(length=3), nullable=False, server_default="MXN"),
        sa.Column("contacto_principal", sa.String(length=150), nullable=True),
        sa.Column("telefono", sa.String(length=30), nullable=True),
        sa.Column("email", sa.String(length=150), nullable=True),
        sa.Column("direccion_calle", sa.String(length=200), nullable=True),
        sa.Column("direccion_numero", sa.String(length=30), nullable=True),
        sa.Column("direccion_colonia", sa.String(length=120), nullable=True),
        sa.Column("direccion_ciudad", sa.String(length=120), nullable=True),
        sa.Column("direccion_estado", sa.String(length=120), nullable=True),
        sa.Column("direccion_codigo_postal", sa.String(length=15), nullable=True),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("notas", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("tipo_persona IN ('fisica', 'moral')", name="ck_proveedor_tipo_persona"),
        sa.CheckConstraint(
            "condiciones_pago IN ('contado', 'credito')", name="ck_proveedor_condiciones_pago",
        ),
    )
    op.alter_column("proveedor", "activo", server_default=None)
    op.create_index(
        "uq_proveedor_codigo_activo", "proveedor", ["codigo"],
        unique=True, postgresql_where=sa.text("activo"),
    )

    op.create_table(
        "producto_proveedor",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column("producto_id", PGUUID(as_uuid=True), sa.ForeignKey("producto.id"), nullable=False),
        sa.Column("proveedor_id", PGUUID(as_uuid=True), sa.ForeignKey("proveedor.id"), nullable=False),
        sa.Column("codigo_proveedor", sa.String(length=60), nullable=True),
        sa.Column("precio_compra", sa.Numeric(12, 2), nullable=False),
        sa.Column("tiempo_entrega_dias", sa.Integer(), nullable=False),
        sa.Column("stock_minimo", sa.Numeric(14, 4), nullable=False),
        sa.Column("stock_maximo", sa.Numeric(14, 4), nullable=True),
        sa.Column("cantidad_reorden", sa.Numeric(14, 4), nullable=False),
        sa.Column("es_proveedor_principal", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("producto_id", "proveedor_id", name="uq_producto_proveedor"),
    )
    op.alter_column("producto_proveedor", "es_proveedor_principal", server_default=None)
    op.alter_column("producto_proveedor", "activo", server_default=None)
    op.create_index(
        "uq_producto_proveedor_principal", "producto_proveedor", ["producto_id"],
        unique=True, postgresql_where=sa.text("es_proveedor_principal AND activo"),
    )

    bind = op.get_bind()
    for codigo, desc, roles in _PERMISOS:
        bind.execute(
            sa.text(
                "INSERT INTO permiso (id, codigo, descripcion) VALUES (:id, :c, :d) "
                "ON CONFLICT (codigo) DO NOTHING"
            ),
            {"id": str(uuid.uuid4()), "c": codigo, "d": desc},
        )
        for rol in roles:
            bind.execute(
                sa.text(
                    "INSERT INTO rol_permiso (rol_id, permiso_id) "
                    "SELECT r.id, p.id FROM rol r, permiso p "
                    "WHERE r.codigo = :rc AND p.codigo = :pc ON CONFLICT DO NOTHING"
                ),
                {"rc": rol, "pc": codigo},
            )


def downgrade() -> None:
    bind = op.get_bind()
    for codigo, _, _ in _PERMISOS:
        bind.execute(
            sa.text(
                "DELETE FROM rol_permiso WHERE permiso_id IN "
                "(SELECT id FROM permiso WHERE codigo = :c)"
            ),
            {"c": codigo},
        )
        bind.execute(sa.text("DELETE FROM permiso WHERE codigo = :c"), {"c": codigo})

    op.drop_index("uq_producto_proveedor_principal", table_name="producto_proveedor")
    op.drop_table("producto_proveedor")
    op.drop_index("uq_proveedor_codigo_activo", table_name="proveedor")
    op.drop_table("proveedor")
