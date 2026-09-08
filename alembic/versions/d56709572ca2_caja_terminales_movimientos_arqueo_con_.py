"""caja: terminales, movimientos, arqueo con conciliacion

- Tabla `caja` (terminal física por sucursal; nombre único entre activas).
- `caja_turno` + `caja_id` (FK caja, backfill 'Caja 1' por sucursal), `nota_cierre`,
  `conciliado_por`, `conciliado_en`; `estado` VARCHAR(20)->(30) para
  'cerrado_con_diferencia'.
- Índices de turno abierto: se reemplaza `uq_caja_turno_abierto (usuario, sucursal)`
  por `uq_caja_turno_abierto_caja (caja_id)` y `uq_caja_turno_abierto_usuario
  (usuario_id)`, ambos WHERE estado='abierto'.
- Tabla `caja_movimiento` (retiro/ingreso/gasto, append-only).
- Tabla `caja_denominacion` (desglose por denominación en apertura/cierre).
- Permisos `caja.autorizar_diferencia`, `caja.ver_historico`, `caja.forzar_cierre`,
  `caja.administrar` -> roles admin, gerente.

Revision ID: d56709572ca2
Revises: b3c4d5e6f7a8
Create Date: 2026-09-08 15:30:51.580821
"""
from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PGUUID


revision: str = "d56709572ca2"
down_revision: Union[str, Sequence[str], None] = "b3c4d5e6f7a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_PERMISOS = [
    ("caja.autorizar_diferencia", "Conciliar/autorizar turnos cerrados con diferencia",
     ("admin", "gerente")),
    ("caja.ver_historico", "Ver el histórico de turnos y arqueos de la sucursal",
     ("admin", "gerente")),
    ("caja.forzar_cierre", "Cerrar el turno de otro cajero (turno abandonado)",
     ("admin", "gerente")),
    ("caja.administrar", "Alta/baja/rename de cajas (terminales) de la sucursal",
     ("admin", "gerente")),
]


def upgrade() -> None:
    # --- caja (terminal física) ---
    op.create_table(
        "caja",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column("sucursal_id", PGUUID(as_uuid=True), sa.ForeignKey("sucursal.id"), nullable=False),
        sa.Column("nombre", sa.String(length=60), nullable=False),
        sa.Column("activa", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.alter_column("caja", "activa", server_default=None)
    op.create_index(
        "uq_caja_nombre_activa", "caja", ["sucursal_id", "nombre"],
        unique=True, postgresql_where=sa.text("activa"),
    )

    # --- caja_movimiento (retiro/ingreso/gasto, append-only) ---
    op.create_table(
        "caja_movimiento",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column("caja_turno_id", PGUUID(as_uuid=True), sa.ForeignKey("caja_turno.id"), nullable=False),
        sa.Column("tipo", sa.String(length=20), nullable=False),
        sa.Column("monto", sa.Numeric(12, 2), nullable=False),
        sa.Column("motivo", sa.Text(), nullable=True),
        sa.Column("usuario_id", PGUUID(as_uuid=True), sa.ForeignKey("usuario.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("tipo IN ('retiro', 'ingreso', 'gasto')", name="ck_caja_movimiento_tipo"),
        sa.CheckConstraint("monto > 0", name="ck_caja_movimiento_monto_pos"),
    )
    op.create_index("ix_caja_movimiento_turno", "caja_movimiento", ["caja_turno_id"])

    # --- caja_denominacion (desglose por denominación) ---
    op.create_table(
        "caja_denominacion",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column("caja_turno_id", PGUUID(as_uuid=True), sa.ForeignKey("caja_turno.id"), nullable=False),
        sa.Column("momento", sa.String(length=10), nullable=False),
        sa.Column("valor", sa.Numeric(12, 2), nullable=False),
        sa.Column("cantidad", sa.Integer(), nullable=False),
        sa.CheckConstraint("momento IN ('apertura', 'cierre')", name="ck_caja_denominacion_momento"),
        sa.CheckConstraint("cantidad >= 0", name="ck_caja_denominacion_cantidad"),
        sa.UniqueConstraint("caja_turno_id", "momento", "valor", name="uq_caja_denominacion"),
    )
    op.create_index("ix_caja_denominacion_turno", "caja_denominacion", ["caja_turno_id"])

    # --- caja_turno: nuevas columnas ---
    op.alter_column("caja_turno", "estado", type_=sa.String(length=30), existing_nullable=False)
    op.add_column(
        "caja_turno",
        sa.Column("caja_id", PGUUID(as_uuid=True), sa.ForeignKey("caja.id"), nullable=True),
    )
    op.add_column("caja_turno", sa.Column("nota_cierre", sa.Text(), nullable=True))
    op.add_column(
        "caja_turno",
        sa.Column("conciliado_por", PGUUID(as_uuid=True), sa.ForeignKey("usuario.id"), nullable=True),
    )
    op.add_column("caja_turno", sa.Column("conciliado_en", sa.DateTime(timezone=True), nullable=True))

    # Backfill: una 'Caja 1' por cada sucursal; apuntar los turnos existentes.
    bind = op.get_bind()
    for (sid,) in bind.execute(sa.text("SELECT id FROM sucursal")).fetchall():
        caja_id = str(uuid.uuid4())
        bind.execute(
            sa.text(
                "INSERT INTO caja (id, sucursal_id, nombre, activa, created_at, updated_at) "
                "VALUES (:id, :sid, 'Caja 1', true, now(), now())"
            ),
            {"id": caja_id, "sid": sid},
        )
        bind.execute(
            sa.text(
                "UPDATE caja_turno SET caja_id = :cid "
                "WHERE sucursal_id = :sid AND caja_id IS NULL"
            ),
            {"cid": caja_id, "sid": sid},
        )
    op.alter_column("caja_turno", "caja_id", nullable=False)

    # --- índices de turno abierto: uno por caja y uno por cajero ---
    op.drop_index("uq_caja_turno_abierto", table_name="caja_turno")
    op.create_index(
        "uq_caja_turno_abierto_caja", "caja_turno", ["caja_id"],
        unique=True, postgresql_where=sa.text("estado = 'abierto'"),
    )
    op.create_index(
        "uq_caja_turno_abierto_usuario", "caja_turno", ["usuario_id"],
        unique=True, postgresql_where=sa.text("estado = 'abierto'"),
    )

    # --- permisos ---
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

    op.drop_index("uq_caja_turno_abierto_usuario", table_name="caja_turno")
    op.drop_index("uq_caja_turno_abierto_caja", table_name="caja_turno")
    op.create_index(
        "uq_caja_turno_abierto", "caja_turno", ["usuario_id", "sucursal_id"],
        unique=True, postgresql_where=sa.text("estado = 'abierto'"),
    )

    op.drop_column("caja_turno", "conciliado_en")
    op.drop_column("caja_turno", "conciliado_por")
    op.drop_column("caja_turno", "nota_cierre")
    op.drop_column("caja_turno", "caja_id")
    op.alter_column("caja_turno", "estado", type_=sa.String(length=20), existing_nullable=False)

    op.drop_index("ix_caja_denominacion_turno", table_name="caja_denominacion")
    op.drop_table("caja_denominacion")
    op.drop_index("ix_caja_movimiento_turno", table_name="caja_movimiento")
    op.drop_table("caja_movimiento")
    op.drop_index("uq_caja_nombre_activa", table_name="caja")
    op.drop_table("caja")
