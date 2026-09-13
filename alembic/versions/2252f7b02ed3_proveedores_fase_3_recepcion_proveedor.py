"""proveedores fase 3: recepcion_proveedor

- Tablas `recepcion_proveedor` (evento inmutable, sin `updated_at`) +
  `recepcion_proveedor_detalle` (con desglose de defectuosos y evidencia).
- Sin cambios en `inventario`: se reusa `movimiento_inventario` tal cual vía
  `AplicarMovimientoUseCase` (ENTRADA/MERMA), `referencia_tipo` es texto libre.
- Permisos `recepcion_proveedor.leer/registrar`.

Revision ID: 2252f7b02ed3
Revises: 6726e66ed368
Create Date: 2026-09-12 00:00:00.000002
"""
from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PGUUID, ARRAY


revision: str = '2252f7b02ed3'
down_revision: Union[str, Sequence[str], None] = '6726e66ed368'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_PERMISOS = [
    ("recepcion_proveedor.leer", "Ver/listar recepciones de mercancía", ("admin", "gerente", "almacenista")),
    ("recepcion_proveedor.registrar", "Registrar la recepción de mercancía de un proveedor",
     ("admin", "gerente", "almacenista")),
]


def upgrade() -> None:
    op.create_table(
        "recepcion_proveedor",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column("pedido_id", PGUUID(as_uuid=True), sa.ForeignKey("pedido_proveedor.id"), nullable=True),
        sa.Column("proveedor_id", PGUUID(as_uuid=True), sa.ForeignKey("proveedor.id"), nullable=False),
        sa.Column("sucursal_id", PGUUID(as_uuid=True), sa.ForeignKey("sucursal.id"), nullable=False),
        sa.Column("numero_factura", sa.String(length=60), nullable=True),
        sa.Column("numero_remision", sa.String(length=60), nullable=True),
        sa.Column("transportista", sa.String(length=120), nullable=True),
        sa.Column("recibido_por", PGUUID(as_uuid=True), sa.ForeignKey("usuario.id"), nullable=False),
        sa.Column("fecha_recepcion", sa.DateTime(timezone=True), nullable=False),
        sa.Column("estado", sa.String(length=20), nullable=False),
        sa.Column("notas", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "estado IN ('completa', 'parcial', 'con_defectos')", name="ck_recepcion_estado",
        ),
    )
    op.create_index("ix_recepcion_proveedor_proveedor", "recepcion_proveedor", ["proveedor_id"])
    op.create_index("ix_recepcion_proveedor_sucursal", "recepcion_proveedor", ["sucursal_id"])
    op.create_index("ix_recepcion_proveedor_pedido", "recepcion_proveedor", ["pedido_id"])

    op.create_table(
        "recepcion_proveedor_detalle",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column(
            "recepcion_id", PGUUID(as_uuid=True),
            sa.ForeignKey("recepcion_proveedor.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("producto_id", PGUUID(as_uuid=True), sa.ForeignKey("producto.id"), nullable=False),
        sa.Column("cantidad_esperada", sa.Numeric(14, 4), nullable=True),
        sa.Column("cantidad_recibida_buena", sa.Numeric(14, 4), nullable=False),
        sa.Column("cantidad_defectuosa", sa.Numeric(14, 4), nullable=False, server_default="0"),
        sa.Column("motivo_defecto", sa.String(length=20), nullable=True),
        sa.Column("accion_defecto", sa.String(length=25), nullable=True),
        sa.Column("fotos_evidencia_keys", ARRAY(sa.String()), nullable=True),
        sa.Column("notas", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "motivo_defecto IS NULL OR motivo_defecto IN "
            "('danado', 'caducado', 'incompleto', 'error_proveedor', 'otro')",
            name="ck_recepcion_detalle_motivo",
        ),
        sa.CheckConstraint(
            "accion_defecto IS NULL OR accion_defecto IN "
            "('devolucion', 'merma', 'aceptado_con_descuento')",
            name="ck_recepcion_detalle_accion",
        ),
    )
    op.alter_column("recepcion_proveedor_detalle", "cantidad_defectuosa", server_default=None)
    op.create_index("ix_recepcion_proveedor_detalle_recepcion", "recepcion_proveedor_detalle", ["recepcion_id"])

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

    op.drop_index("ix_recepcion_proveedor_detalle_recepcion", table_name="recepcion_proveedor_detalle")
    op.drop_table("recepcion_proveedor_detalle")
    op.drop_index("ix_recepcion_proveedor_pedido", table_name="recepcion_proveedor")
    op.drop_index("ix_recepcion_proveedor_sucursal", table_name="recepcion_proveedor")
    op.drop_index("ix_recepcion_proveedor_proveedor", table_name="recepcion_proveedor")
    op.drop_table("recepcion_proveedor")
