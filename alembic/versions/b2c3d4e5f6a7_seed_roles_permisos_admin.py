"""Seed de permisos, roles base, asignaciones rol-permiso y usuario admin inicial

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-08-30 23:25:00.000000

Idempotente: correrla dos veces no duplica ni falla (INSERT ... ON CONFLICT DO NOTHING).
El usuario admin inicial se crea SOLO si no existe ya un admin activo, leyendo las
credenciales de SEED_ADMIN_EMAIL / SEED_ADMIN_PASSWORD. Si no están definidas y hace
falta crearlo, la migración falla con un mensaje claro (no se crea un admin con
contraseña por defecto).
"""
from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa

from app.core.config import settings
from app.core.security import get_password_hash


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# --- Catálogo de permisos (modulo.accion) ---
PERMISOS: list[tuple[str, str]] = [
    ("usuarios.crear", "Crear usuarios"),
    ("usuarios.leer", "Ver/listar usuarios"),
    ("usuarios.editar", "Editar datos de usuario"),
    ("usuarios.desactivar", "Dar de baja (soft delete) a un usuario"),
    ("roles.gestionar", "Crear/editar roles y asignar permisos"),
    ("inventario.crear", "Crear productos/categorías"),
    ("inventario.editar", "Editar productos/categorías"),
    ("inventario.leer", "Consultar productos, categorías, existencias"),
    ("inventario.movimiento", "Registrar entradas/salidas de stock"),
    ("clientes.crear", "Crear clientes"),
    ("clientes.leer", "Ver/listar clientes"),
    ("clientes.editar", "Editar clientes"),
    ("clientes.eliminar", "Eliminar/desactivar clientes"),
    ("ventas.crear", "Registrar una venta"),
    ("ventas.leer", "Ver/listar ventas"),
    ("ventas.anular", "Cancelar/anular una venta"),
    ("reportes.leer", "Consultar reportes (corte de caja, etc.)"),
    ("auditoria.leer", "Consultar el log de auditoría"),
]

# --- Roles base ---
ROLES: list[tuple[str, str, str]] = [
    ("admin", "Administrador", "Acceso total al sistema"),
    ("gerente", "Gerente", "Gestión operativa de sucursal(es)"),
    ("cajero", "Cajero", "Registro de ventas en punto de venta"),
    ("almacenista", "Almacenista", "Gestión de inventario y stock"),
]

# --- Asignación rol -> permisos ---
# "admin" se calcula dinámicamente (todos los permisos del catálogo).
ASIGNACIONES: dict[str, list[str]] = {
    "gerente": [
        "inventario.crear", "inventario.editar", "inventario.leer", "inventario.movimiento",
        "clientes.crear", "clientes.leer", "clientes.editar", "clientes.eliminar",
        "ventas.leer", "ventas.anular",
        "reportes.leer",
        "usuarios.leer",
    ],
    "cajero": [
        "ventas.crear", "ventas.leer",
        "clientes.crear", "clientes.leer",
        "inventario.leer",
    ],
    "almacenista": [
        "inventario.crear", "inventario.editar", "inventario.leer", "inventario.movimiento",
    ],
}


def upgrade() -> None:
    bind = op.get_bind()

    # 1. Permisos (idempotente)
    for codigo, descripcion in PERMISOS:
        bind.execute(
            sa.text(
                "INSERT INTO permiso (id, codigo, descripcion) "
                "VALUES (:id, :codigo, :descripcion) "
                "ON CONFLICT (codigo) DO NOTHING"
            ),
            {"id": str(uuid.uuid4()), "codigo": codigo, "descripcion": descripcion},
        )

    # 2. Roles base (idempotente)
    for codigo, nombre, descripcion in ROLES:
        bind.execute(
            sa.text(
                "INSERT INTO rol (id, codigo, nombre, descripcion) "
                "VALUES (:id, :codigo, :nombre, :descripcion) "
                "ON CONFLICT (codigo) DO NOTHING"
            ),
            {"id": str(uuid.uuid4()), "codigo": codigo, "nombre": nombre, "descripcion": descripcion},
        )

    # 3. Asignación rol -> permiso
    # admin: todos los permisos del catálogo
    bind.execute(
        sa.text(
            "INSERT INTO rol_permiso (rol_id, permiso_id) "
            "SELECT r.id, p.id FROM rol r CROSS JOIN permiso p "
            "WHERE r.codigo = 'admin' "
            "ON CONFLICT DO NOTHING"
        )
    )
    for rol_codigo, permisos in ASIGNACIONES.items():
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

    # 4. Usuario admin inicial (solo si no hay ningún admin activo)
    hay_admin = bind.execute(
        sa.text(
            "SELECT 1 FROM usuario u JOIN rol r ON u.rol_id = r.id "
            "WHERE r.codigo = 'admin' AND u.activo = true LIMIT 1"
        )
    ).first()

    if not hay_admin:
        email = settings.seed_admin_email
        password = settings.seed_admin_password
        if not email or not password:
            raise RuntimeError(
                "No existe un usuario admin activo y no se pueden crear las credenciales "
                "iniciales: definí SEED_ADMIN_EMAIL y SEED_ADMIN_PASSWORD en el entorno "
                "antes de correr esta migración."
            )

        rol_admin_id = bind.execute(
            sa.text("SELECT id FROM rol WHERE codigo = 'admin'")
        ).scalar_one()

        bind.execute(
            sa.text(
                "INSERT INTO usuario "
                "(id, sucursal_id, rol_id, nombre, email, password_hash, "
                " last_login_at, created_at, updated_at, activo) "
                "VALUES "
                "(:id, NULL, :rol_id, :nombre, :email, :password_hash, "
                " NULL, now(), now(), true) "
                "ON CONFLICT (email) DO NOTHING"
            ),
            {
                "id": str(uuid.uuid4()),
                "rol_id": str(rol_admin_id),
                "nombre": settings.seed_admin_nombre,
                "email": email,
                "password_hash": get_password_hash(password),
            },
        )


def downgrade() -> None:
    bind = op.get_bind()

    # Borra exactamente lo insertado, por código (no TRUNCATE).
    if settings.seed_admin_email:
        bind.execute(
            sa.text(
                "DELETE FROM refresh_token WHERE usuario_id IN "
                "(SELECT id FROM usuario WHERE email = :email)"
            ),
            {"email": settings.seed_admin_email},
        )
        bind.execute(
            sa.text("DELETE FROM usuario WHERE email = :email"),
            {"email": settings.seed_admin_email},
        )

    codigos_permisos = [c for c, _ in PERMISOS]
    codigos_roles = [c for c, _, _ in ROLES]

    bind.execute(
        sa.text(
            "DELETE FROM rol_permiso WHERE rol_id IN "
            "(SELECT id FROM rol WHERE codigo = ANY(:roles))"
        ),
        {"roles": codigos_roles},
    )
    bind.execute(
        sa.text("DELETE FROM rol WHERE codigo = ANY(:roles)"),
        {"roles": codigos_roles},
    )
    bind.execute(
        sa.text("DELETE FROM permiso WHERE codigo = ANY(:permisos)"),
        {"permisos": codigos_permisos},
    )
