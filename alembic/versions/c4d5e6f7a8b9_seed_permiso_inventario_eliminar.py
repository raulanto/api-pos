"""Seed del permiso inventario.eliminar

Nuevo permiso para el borrado FÍSICO de un producto (DELETE /productos/{id}),
distinto de `inventario.editar` (que cubre la baja lógica /desactivar).

Asignación:
- admin: sí.
- gerente: sí (limpieza de catálogo de productos nunca usados).
- almacenista: sí (ya gestiona el inventario: crear/editar/movimiento).
- cajero: no (solo lectura de inventario).

Idempotente: `INSERT ... ON CONFLICT DO NOTHING`.

Revision ID: c4d5e6f7a8b9
Revises: b3d4e5f6a7c8
Create Date: 2026-09-05 00:00:00.000000
"""
from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa


revision: str = "c4d5e6f7a8b9"
down_revision: Union[str, Sequence[str], None] = "b3d4e5f6a7c8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_CODIGO = "inventario.eliminar"
_DESCRIPCION = "Borrar físicamente productos (solo sin historial)"
_ROLES = ["admin", "gerente", "almacenista"]


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "INSERT INTO permiso (id, codigo, descripcion) "
            "VALUES (:id, :c, :d) ON CONFLICT (codigo) DO NOTHING"
        ),
        {"id": str(uuid.uuid4()), "c": _CODIGO, "d": _DESCRIPCION},
    )
    for rol_codigo in _ROLES:
        bind.execute(
            sa.text(
                "INSERT INTO rol_permiso (rol_id, permiso_id) "
                "SELECT r.id, p.id FROM rol r, permiso p "
                "WHERE r.codigo = :rc AND p.codigo = :pc "
                "ON CONFLICT DO NOTHING"
            ),
            {"rc": rol_codigo, "pc": _CODIGO},
        )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "DELETE FROM rol_permiso WHERE permiso_id IN "
            "(SELECT id FROM permiso WHERE codigo = :c)"
        ),
        {"c": _CODIGO},
    )
    bind.execute(sa.text("DELETE FROM permiso WHERE codigo = :c"), {"c": _CODIGO})
