"""Monedero electrónico (cashback por teléfono).

- `monedero_cuenta` (saldo por teléfono) + `monedero_movimiento` (ledger).
- `venta.telefono` (historial por teléfono) + `venta.monedero_generado`.
- `producto` / `producto_unidad`: `monedero_pct` + `monedero_monto`.
- `devolucion`: método `monedero` aceptado (recrea el CHECK).
- Permiso `monedero.ajustar` (admin, gerente).

Revision ID: d3e4f5a6b7c8
Revises: c2d3e4f5a6b7
Create Date: 2026-09-07 00:00:00.000000
"""
import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PGUUID


revision: str = "d3e4f5a6b7c8"
down_revision: Union[str, Sequence[str], None] = "c2d3e4f5a6b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_PERMISOS = [
    ("monedero.ajustar", "Ajustar manualmente el saldo del monedero de un cliente",
     ("admin", "gerente")),
]


def upgrade() -> None:
    op.create_table(
        "monedero_cuenta",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column("telefono", sa.String(length=50), nullable=False),
        sa.Column("saldo", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("telefono", name="uq_monedero_cuenta_telefono"),
    )

    op.create_table(
        "monedero_movimiento",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column(
            "cuenta_id", PGUUID(as_uuid=True),
            sa.ForeignKey("monedero_cuenta.id"), nullable=False,
        ),
        sa.Column("tipo", sa.String(length=30), nullable=False),
        sa.Column("monto", sa.Numeric(12, 2), nullable=False),
        sa.Column("saldo_resultante", sa.Numeric(12, 2), nullable=False),
        sa.Column("venta_id", PGUUID(as_uuid=True), sa.ForeignKey("venta.id"), nullable=True),
        sa.Column("usuario_id", PGUUID(as_uuid=True), sa.ForeignKey("usuario.id"), nullable=True),
        sa.Column("motivo", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "tipo IN ('acumulacion', 'consumo', 'reverso_acumulacion', "
            "'reverso_consumo', 'ajuste')",
            name="ck_monedero_movimiento_tipo",
        ),
    )
    op.create_index("ix_monedero_movimiento_cuenta", "monedero_movimiento", ["cuenta_id"])
    op.create_index("ix_monedero_movimiento_venta", "monedero_movimiento", ["venta_id"])

    # venta: teléfono (historial) + monedero generado (congelado)
    op.add_column("venta", sa.Column("telefono", sa.String(length=50), nullable=True))
    op.create_index("ix_venta_telefono", "venta", ["telefono"])
    op.add_column(
        "venta",
        sa.Column("monedero_generado", sa.Numeric(12, 2), nullable=False, server_default="0"),
    )
    op.alter_column("venta", "monedero_generado", server_default=None)

    # producto / producto_unidad: config de acumulación
    for tabla in ("producto", "producto_unidad"):
        op.add_column(tabla, sa.Column("monedero_pct", sa.Numeric(5, 2), nullable=True))
        op.add_column(tabla, sa.Column("monedero_monto", sa.Numeric(12, 2), nullable=True))

    # devolucion: aceptar metodo 'monedero'
    op.drop_constraint("ck_devolucion_metodo", "devolucion", type_="check")
    op.create_check_constraint(
        "ck_devolucion_metodo", "devolucion",
        "metodo_devolucion IN ('efectivo', 'tarjeta', 'credito', 'monedero')",
    )

    # permisos
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
    for codigo, _desc, _roles in _PERMISOS:
        bind.execute(
            sa.text(
                "DELETE FROM rol_permiso WHERE permiso_id = "
                "(SELECT id FROM permiso WHERE codigo = :c)"
            ),
            {"c": codigo},
        )
        bind.execute(sa.text("DELETE FROM permiso WHERE codigo = :c"), {"c": codigo})

    op.drop_constraint("ck_devolucion_metodo", "devolucion", type_="check")
    op.create_check_constraint(
        "ck_devolucion_metodo", "devolucion",
        "metodo_devolucion IN ('efectivo', 'tarjeta', 'credito')",
    )

    for tabla in ("producto", "producto_unidad"):
        op.drop_column(tabla, "monedero_monto")
        op.drop_column(tabla, "monedero_pct")

    op.drop_index("ix_venta_telefono", table_name="venta")
    op.drop_column("venta", "monedero_generado")
    op.drop_column("venta", "telefono")

    op.drop_index("ix_monedero_movimiento_venta", table_name="monedero_movimiento")
    op.drop_index("ix_monedero_movimiento_cuenta", table_name="monedero_movimiento")
    op.drop_table("monedero_movimiento")
    op.drop_table("monedero_cuenta")
