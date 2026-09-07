"""Ventas: devoluciones parciales, permiso caja.operar y candado de turno único.

- Tablas `devolucion` + `devolucion_linea`.
- Columna `detalle_venta.cantidad_devuelta` (NOT NULL, backfill 0).
- Índice único parcial `uq_caja_turno_abierto` (usuario, sucursal) WHERE
  estado='abierto' — un turno abierto por cajero, a prueba de carrera. Antes
  cierra duplicados existentes dejando el más reciente.
- Permisos `caja.operar` (admin/gerente/cajero) y `ventas.devolver`
  (admin/gerente/cajero).

Revision ID: b1c2d3e4f5a6
Revises: a9b0c1d2e3f4
Create Date: 2026-09-07 00:00:00.000000
"""
from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PGUUID


revision: str = "b1c2d3e4f5a6"
down_revision: Union[str, Sequence[str], None] = "a9b0c1d2e3f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_PERMISOS = [
    ("caja.operar", "Abrir/cerrar turno de caja y ver su arqueo", ("admin", "gerente", "cajero")),
    ("ventas.devolver", "Registrar devoluciones (parciales o totales) de una venta",
     ("admin", "gerente", "cajero")),
]


def upgrade() -> None:
    op.create_table(
        "devolucion",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column("venta_id", PGUUID(as_uuid=True), sa.ForeignKey("venta.id"), nullable=False),
        sa.Column("caja_turno_id", PGUUID(as_uuid=True), sa.ForeignKey("caja_turno.id"), nullable=False),
        sa.Column("usuario_id", PGUUID(as_uuid=True), sa.ForeignKey("usuario.id"), nullable=False),
        sa.Column("motivo", sa.Text(), nullable=True),
        sa.Column("monto_devuelto", sa.Numeric(12, 2), nullable=False),
        sa.Column("metodo_devolucion", sa.String(length=20), nullable=False),
        sa.Column("idempotency_key", sa.String(length=80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "metodo_devolucion IN ('efectivo', 'tarjeta', 'credito')",
            name="ck_devolucion_metodo",
        ),
        sa.UniqueConstraint("idempotency_key", name="uq_devolucion_idempotency_key"),
    )
    op.create_index("ix_devolucion_venta", "devolucion", ["venta_id"])
    op.create_index("ix_devolucion_turno", "devolucion", ["caja_turno_id"])

    op.create_table(
        "devolucion_linea",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column(
            "devolucion_id", PGUUID(as_uuid=True),
            sa.ForeignKey("devolucion.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "detalle_venta_id", PGUUID(as_uuid=True),
            sa.ForeignKey("detalle_venta.id"), nullable=False,
        ),
        sa.Column("cantidad", sa.Numeric(14, 4), nullable=False),
        sa.Column("monto", sa.Numeric(12, 2), nullable=False),
    )
    op.create_index("ix_devolucion_linea_devolucion", "devolucion_linea", ["devolucion_id"])

    op.add_column(
        "detalle_venta",
        sa.Column("cantidad_devuelta", sa.Numeric(14, 4), nullable=False, server_default="0"),
    )
    op.alter_column("detalle_venta", "cantidad_devuelta", server_default=None)

    # Turno único abierto por (usuario, sucursal). Cierra duplicados previos.
    op.execute(
        """
        UPDATE caja_turno SET estado = 'cerrado', cerrado_en = now()
        WHERE estado = 'abierto' AND id NOT IN (
            SELECT DISTINCT ON (usuario_id, sucursal_id) id
            FROM caja_turno WHERE estado = 'abierto'
            ORDER BY usuario_id, sucursal_id, abierto_en DESC
        )
        """
    )
    op.create_index(
        "uq_caja_turno_abierto", "caja_turno", ["usuario_id", "sucursal_id"],
        unique=True, postgresql_where=sa.text("estado = 'abierto'"),
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

    op.drop_index("uq_caja_turno_abierto", table_name="caja_turno")
    op.drop_column("detalle_venta", "cantidad_devuelta")
    op.drop_index("ix_devolucion_linea_devolucion", table_name="devolucion_linea")
    op.drop_table("devolucion_linea")
    op.drop_index("ix_devolucion_turno", table_name="devolucion")
    op.drop_index("ix_devolucion_venta", table_name="devolucion")
    op.drop_table("devolucion")
