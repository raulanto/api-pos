"""Seed de permisos del catálogo de sucursales

Añade los permisos `sucursales.leer|crear|editar|desactivar` y los asigna:
- admin: los cuatro.
- gerente: leer + editar (gestión operativa).
- cajero / almacenista: solo leer (poblar selects).

Idempotente: `INSERT ... ON CONFLICT DO NOTHING`.

Revision ID: a7b8c9d0e1f2
Revises: f1a2b3c4d5e6
Create Date: 2026-09-01 00:00:00.000000
"""
from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa


revision: str = "a7b8c9d0e1f2"
down_revision: Union[str, Sequence[str], None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_PERMISOS: list[tuple[str, str]] = [
    ("sucursales.leer", "Ver/listar sucursales"),
    ("sucursales.crear", "Crear sucursales"),
    ("sucursales.editar", "Editar sucursales"),
    ("sucursales.desactivar", "Desactivar/reactivar sucursales"),
]

_ASIGNACIONES: dict[str, list[str]] = {
    "admin": [c for c, _ in _PERMISOS],
    "gerente": ["sucursales.leer", "sucursales.editar"],
    "cajero": ["sucursales.leer"],
    "almacenista": ["sucursales.leer"],
}


def upgrade() -> None:
    bind = op.get_bind()

    for codigo, descripcion in _PERMISOS:
        bind.execute(
            sa.text(
                "INSERT INTO permiso (id, codigo, descripcion) "
                "VALUES (:id, :c, :d) ON CONFLICT (codigo) DO NOTHING"
            ),
            {"id": str(uuid.uuid4()), "c": codigo, "d": descripcion},
        )

    for rol_codigo, permisos in _ASIGNACIONES.items():
        for permiso_codigo in permisos:
            bind.execute(
                sa.text(
                    "INSERT INTO rol_permiso (rol_id, permiso_id) "
                    "SELECT r.id, p.id FROM rol r, permiso p "
                    "WHERE r.codigo = :rc AND p.codigo = :pc "
                    "ON CONFLICT DO NOTHING"
                ),
                {"rc": rol_codigo, "pc": permiso_codigo},
            )


def downgrade() -> None:
    bind = op.get_bind()
    codigos = [c for c, _ in _PERMISOS]
    bind.execute(
        sa.text(
            "DELETE FROM rol_permiso WHERE permiso_id IN "
            "(SELECT id FROM permiso WHERE codigo = ANY(:c))"
        ),
        {"c": codigos},
    )
    bind.execute(sa.text("DELETE FROM permiso WHERE codigo = ANY(:c)"), {"c": codigos})
