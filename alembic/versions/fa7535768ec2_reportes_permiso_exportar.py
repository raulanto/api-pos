"""reportes: permiso `reportes.exportar`

Exportar (PDF/Excel/CSV) es más sensible que solo leer: puede sacar datos
(montos, márgenes) de la app hacia un archivo. Separado de `reportes.leer`.

Revision ID: fa7535768ec2
Revises: 126350173815
Create Date: 2026-09-13 00:00:00.000000
"""
from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa


revision: str = 'fa7535768ec2'
down_revision: Union[str, Sequence[str], None] = '126350173815'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_CODIGO = "reportes.exportar"
_DESCRIPCION = "Exportar reportes a PDF/Excel/CSV"
_ROLES = ("admin", "gerente")


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "INSERT INTO permiso (id, codigo, descripcion) VALUES (:id, :c, :d) "
            "ON CONFLICT (codigo) DO NOTHING"
        ),
        {"id": str(uuid.uuid4()), "c": _CODIGO, "d": _DESCRIPCION},
    )
    for rol in _ROLES:
        bind.execute(
            sa.text(
                "INSERT INTO rol_permiso (rol_id, permiso_id) "
                "SELECT r.id, p.id FROM rol r, permiso p "
                "WHERE r.codigo = :rc AND p.codigo = :pc ON CONFLICT DO NOTHING"
            ),
            {"rc": rol, "pc": _CODIGO},
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
