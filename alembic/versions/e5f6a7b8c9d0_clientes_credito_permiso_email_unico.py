"""Clientes: permiso clientes.credito.gestionar + email único entre activos

- Nuevo permiso `clientes.credito.gestionar`, asignado a admin y gerente.
- Índice único parcial sobre `cliente.email` para clientes activos.

Revision ID: e5f6a7b8c9d0
Revises: 23e85126655d
Create Date: 2026-08-31 00:00:00.000000
"""
from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa


revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, Sequence[str], None] = "23e85126655d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_PERMISO = "clientes.credito.gestionar"
_DESC = "Cambiar el límite de crédito de un cliente"
_ROLES = ("admin", "gerente")


def upgrade() -> None:
    bind = op.get_bind()

    bind.execute(
        sa.text(
            "INSERT INTO permiso (id, codigo, descripcion) VALUES (:id, :c, :d) "
            "ON CONFLICT (codigo) DO NOTHING"
        ),
        {"id": str(uuid.uuid4()), "c": _PERMISO, "d": _DESC},
    )
    for rol in _ROLES:
        bind.execute(
            sa.text(
                "INSERT INTO rol_permiso (rol_id, permiso_id) "
                "SELECT r.id, p.id FROM rol r, permiso p "
                "WHERE r.codigo = :rc AND p.codigo = :pc "
                "ON CONFLICT DO NOTHING"
            ),
            {"rc": rol, "pc": _PERMISO},
        )

    op.create_index(
        "uq_cliente_email_activo", "cliente", ["email"],
        unique=True, postgresql_where=sa.text("activo"),
    )


def downgrade() -> None:
    op.drop_index("uq_cliente_email_activo", table_name="cliente")
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "DELETE FROM rol_permiso WHERE permiso_id IN (SELECT id FROM permiso WHERE codigo = :c)"
        ),
        {"c": _PERMISO},
    )
    bind.execute(sa.text("DELETE FROM permiso WHERE codigo = :c"), {"c": _PERMISO})
