"""proveedores fase 4: devolucion_proveedor

- Tablas `devolucion_proveedor` (estado pendiente/enviada/cerrada + resultado
  aceptada/rechazada, separados) + `devolucion_proveedor_detalle`.
- Permisos `devolucion_proveedor.leer/gestionar`.

Revision ID: 126350173815
Revises: 2252f7b02ed3
Create Date: 2026-09-12 00:00:00.000003
"""
from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PGUUID


revision: str = '126350173815'
down_revision: Union[str, Sequence[str], None] = '2252f7b02ed3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_PERMISOS = [
    ("devolucion_proveedor.leer", "Ver/listar devoluciones a proveedor", ("admin", "gerente", "almacenista")),
    ("devolucion_proveedor.gestionar", "Crear, enviar y cerrar devoluciones a proveedor",
     ("admin", "gerente", "almacenista")),
]


def upgrade() -> None:
    op.create_table(
        "devolucion_proveedor",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column("proveedor_id", PGUUID(as_uuid=True), sa.ForeignKey("proveedor.id"), nullable=False),
        sa.Column(
            "recepcion_id", PGUUID(as_uuid=True), sa.ForeignKey("recepcion_proveedor.id"), nullable=False,
        ),
        sa.Column("creado_por", PGUUID(as_uuid=True), sa.ForeignKey("usuario.id"), nullable=False),
        sa.Column("estado", sa.String(length=20), nullable=False),
        sa.Column("resultado", sa.String(length=20), nullable=True),
        sa.Column("tipo_resolucion", sa.String(length=20), nullable=True),
        sa.Column("fecha_envio", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fecha_cierre", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notas", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "estado IN ('pendiente', 'enviada', 'cerrada')", name="ck_devolucion_prov_estado",
        ),
        sa.CheckConstraint(
            "resultado IS NULL OR resultado IN ('aceptada_proveedor', 'rechazada_proveedor')",
            name="ck_devolucion_prov_resultado",
        ),
        sa.CheckConstraint(
            "tipo_resolucion IS NULL OR tipo_resolucion IN "
            "('reemplazo', 'nota_credito', 'reembolso')",
            name="ck_devolucion_prov_resolucion",
        ),
    )
    op.create_index("ix_devolucion_prov_proveedor", "devolucion_proveedor", ["proveedor_id"])
    op.create_index("ix_devolucion_prov_recepcion", "devolucion_proveedor", ["recepcion_id"])

    op.create_table(
        "devolucion_proveedor_detalle",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column(
            "devolucion_id", PGUUID(as_uuid=True),
            sa.ForeignKey("devolucion_proveedor.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "recepcion_detalle_id", PGUUID(as_uuid=True),
            sa.ForeignKey("recepcion_proveedor_detalle.id"), nullable=False,
        ),
        sa.Column("producto_id", PGUUID(as_uuid=True), sa.ForeignKey("producto.id"), nullable=False),
        sa.Column("cantidad", sa.Numeric(14, 4), nullable=False),
    )
    op.create_index(
        "ix_devolucion_prov_detalle_devolucion", "devolucion_proveedor_detalle", ["devolucion_id"],
    )
    op.create_index(
        "ix_devolucion_prov_detalle_recepcion_detalle", "devolucion_proveedor_detalle",
        ["recepcion_detalle_id"],
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

    op.drop_index(
        "ix_devolucion_prov_detalle_recepcion_detalle", table_name="devolucion_proveedor_detalle",
    )
    op.drop_index("ix_devolucion_prov_detalle_devolucion", table_name="devolucion_proveedor_detalle")
    op.drop_table("devolucion_proveedor_detalle")
    op.drop_index("ix_devolucion_prov_recepcion", table_name="devolucion_proveedor")
    op.drop_index("ix_devolucion_prov_proveedor", table_name="devolucion_proveedor")
    op.drop_table("devolucion_proveedor")
