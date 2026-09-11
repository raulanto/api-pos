"""agenda: recursos, disponibilidad, citas y cola de oferta

- `producto` + `duracion_minutos`/`tiempo_buffer_minutos`/`requiere_recurso`/
  `disponibilidad_cruzada_activa` (un servicio es agendable si tiene
  `duracion_minutos`, el `tipo=servicio` solo no alcanza).
- Catálogo: `recurso` (terminal física, nombre único entre activos de la
  sucursal), `empleado_servicio` (qué usuario atiende qué servicio),
  `disponibilidad_horario` (horario recurrente semanal), `disponibilidad_excepcion`
  (bloqueo / horario especial puntual), `disponibilidad_recurso` (horario propio
  opcional de un recurso).
- `cita` + `cita_asignacion` (cola de oferta paralela: una fila `ofrecida` por
  candidato, gana el primero en aceptar).
- Único choque *duro*: un `recurso` no puede estar en dos citas
  `asignada`/`en_proceso` que se solapen — `EXCLUDE USING gist` (extensión
  `btree_gist`). El choque de empleado es una regla de aplicación, no de BD
  (el negocio permite varias ofertas simultáneas al mismo empleado).
- Rol `empleado` + permisos `agenda.administrar`, `citas.gestionar`,
  `citas.ver_propias`, `citas.responder_oferta`.

Revision ID: 642e7dd5ecb1
Revises: c0d1e2f3a4b5
Create Date: 2026-09-11 12:53:27.807923
"""
from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PGUUID


revision: str = '642e7dd5ecb1'
down_revision: Union[str, Sequence[str], None] = 'c0d1e2f3a4b5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ROLES = [
    ("empleado", "Empleado", "Atiende servicios agendados; ve y responde sus propias citas"),
]

_PERMISOS = [
    ("agenda.administrar", "Alta/baja de recursos, horarios y calificación de empleados",
     ("admin", "gerente")),
    ("citas.gestionar", "Crear, reasignar, cancelar y facturar cualquier cita",
     ("admin", "gerente", "cajero")),
    ("citas.ver_propias", "Ver las citas propias (ofertadas o asignadas)",
     ("admin", "gerente", "cajero", "empleado")),
    ("citas.responder_oferta", "Aceptar o rechazar una oferta de cita propia",
     ("admin", "gerente", "cajero", "empleado")),
]


def upgrade() -> None:
    # --- producto: campos de agenda ---
    op.add_column("producto", sa.Column("duracion_minutos", sa.Integer(), nullable=True))
    op.add_column(
        "producto",
        sa.Column("tiempo_buffer_minutos", sa.Integer(), nullable=False, server_default="0"),
    )
    op.alter_column("producto", "tiempo_buffer_minutos", server_default=None)
    op.add_column(
        "producto",
        sa.Column("requiere_recurso", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.alter_column("producto", "requiere_recurso", server_default=None)
    op.add_column(
        "producto",
        sa.Column(
            "disponibilidad_cruzada_activa", sa.Boolean(), nullable=False,
            server_default=sa.false(),
        ),
    )
    op.alter_column("producto", "disponibilidad_cruzada_activa", server_default=None)

    # --- recurso ---
    op.create_table(
        "recurso",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column("sucursal_id", PGUUID(as_uuid=True), sa.ForeignKey("sucursal.id"), nullable=False),
        sa.Column("nombre", sa.String(length=80), nullable=False),
        sa.Column("tipo", sa.String(length=30), nullable=True),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.alter_column("recurso", "activo", server_default=None)
    op.create_index(
        "uq_recurso_nombre_activo", "recurso", ["sucursal_id", "nombre"],
        unique=True, postgresql_where=sa.text("activo"),
    )

    # --- empleado_servicio ---
    op.create_table(
        "empleado_servicio",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column("empleado_id", PGUUID(as_uuid=True), sa.ForeignKey("usuario.id"), nullable=False),
        sa.Column("servicio_id", PGUUID(as_uuid=True), sa.ForeignKey("producto.id"), nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("empleado_id", "servicio_id", name="uq_empleado_servicio"),
    )
    op.alter_column("empleado_servicio", "activo", server_default=None)

    # --- disponibilidad_horario ---
    op.create_table(
        "disponibilidad_horario",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column("empleado_id", PGUUID(as_uuid=True), sa.ForeignKey("usuario.id"), nullable=False),
        sa.Column("sucursal_id", PGUUID(as_uuid=True), sa.ForeignKey("sucursal.id"), nullable=False),
        sa.Column("dia_semana", sa.SmallInteger(), nullable=False),
        sa.Column("hora_inicio", sa.Time(), nullable=False),
        sa.Column("hora_fin", sa.Time(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_disponibilidad_horario_empleado", "disponibilidad_horario", ["empleado_id"])

    # --- disponibilidad_excepcion ---
    op.create_table(
        "disponibilidad_excepcion",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column("empleado_id", PGUUID(as_uuid=True), sa.ForeignKey("usuario.id"), nullable=False),
        sa.Column("fecha", sa.Date(), nullable=False),
        sa.Column("tipo", sa.String(length=20), nullable=False),
        sa.Column("hora_inicio", sa.Time(), nullable=True),
        sa.Column("hora_fin", sa.Time(), nullable=True),
        sa.Column("motivo", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "tipo IN ('bloqueo', 'horario_especial')", name="ck_disponibilidad_excepcion_tipo",
        ),
    )
    op.create_index(
        "ix_disponibilidad_excepcion_empleado_fecha", "disponibilidad_excepcion",
        ["empleado_id", "fecha"],
    )

    # --- disponibilidad_recurso ---
    op.create_table(
        "disponibilidad_recurso",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column("recurso_id", PGUUID(as_uuid=True), sa.ForeignKey("recurso.id"), nullable=False),
        sa.Column("dia_semana", sa.SmallInteger(), nullable=False),
        sa.Column("hora_inicio", sa.Time(), nullable=False),
        sa.Column("hora_fin", sa.Time(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_disponibilidad_recurso_recurso", "disponibilidad_recurso", ["recurso_id"])

    # --- cita ---
    op.create_table(
        "cita",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column("servicio_id", PGUUID(as_uuid=True), sa.ForeignKey("producto.id"), nullable=False),
        sa.Column("sucursal_id", PGUUID(as_uuid=True), sa.ForeignKey("sucursal.id"), nullable=False),
        sa.Column("cliente_id", PGUUID(as_uuid=True), sa.ForeignKey("cliente.id"), nullable=True),
        sa.Column("recurso_id", PGUUID(as_uuid=True), sa.ForeignKey("recurso.id"), nullable=True),
        sa.Column("empleado_id", PGUUID(as_uuid=True), sa.ForeignKey("usuario.id"), nullable=True),
        sa.Column("fecha_hora_inicio", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fecha_hora_fin", sa.DateTime(timezone=True), nullable=False),
        sa.Column("estado", sa.String(length=30), nullable=False),
        sa.Column("disponibilidad_cruzada", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("politica_cancelacion_horas", sa.Integer(), nullable=True),
        sa.Column("penalizacion_cancelacion", sa.Numeric(12, 2), nullable=True),
        sa.Column("motivo_cancelacion", sa.Text(), nullable=True),
        sa.Column("venta_detalle_id", PGUUID(as_uuid=True), sa.ForeignKey("detalle_venta.id"), nullable=True),
        sa.Column("creado_por_usuario_id", PGUUID(as_uuid=True), sa.ForeignKey("usuario.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.alter_column("cita", "disponibilidad_cruzada", server_default=None)
    op.create_index("ix_cita_empleado", "cita", ["empleado_id"])
    op.create_index("ix_cita_sucursal", "cita", ["sucursal_id"])

    # --- cita_asignacion ---
    op.create_table(
        "cita_asignacion",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column(
            "cita_id", PGUUID(as_uuid=True), sa.ForeignKey("cita.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("empleado_id", PGUUID(as_uuid=True), sa.ForeignKey("usuario.id"), nullable=False),
        sa.Column("estado", sa.String(length=20), nullable=False),
        sa.Column("fecha_oferta", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("fecha_respuesta", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "estado IN ('ofrecida', 'aceptada', 'rechazada', 'superada')",
            name="ck_cita_asignacion_estado",
        ),
    )
    op.create_index("ix_cita_asignacion_cita", "cita_asignacion", ["cita_id"])
    op.create_index("ix_cita_asignacion_empleado_estado", "cita_asignacion", ["empleado_id", "estado"])

    # --- choque físico duro sobre `recurso`: EXCLUDE nativo de Postgres ---
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    op.execute(
        "ALTER TABLE cita ADD CONSTRAINT ck_cita_recurso_sin_solape "
        "EXCLUDE USING gist ("
        "  recurso_id WITH =, "
        "  tstzrange(fecha_hora_inicio, fecha_hora_fin, '[)') WITH &&"
        ") WHERE (recurso_id IS NOT NULL AND estado IN ('asignada', 'en_proceso'))"
    )

    # --- roles + permisos ---
    bind = op.get_bind()
    for codigo, nombre, descripcion in _ROLES:
        bind.execute(
            sa.text(
                "INSERT INTO rol (id, codigo, nombre, descripcion) "
                "VALUES (:id, :c, :n, :d) ON CONFLICT (codigo) DO NOTHING"
            ),
            {"id": str(uuid.uuid4()), "c": codigo, "n": nombre, "d": descripcion},
        )
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
    # Si ya hay usuarios con rol 'empleado', el FK frena este DELETE a propósito
    # (downgrade no borra cuentas de usuario silenciosamente).
    for codigo, _, _ in _ROLES:
        bind.execute(sa.text("DELETE FROM rol WHERE codigo = :c"), {"c": codigo})

    op.execute("ALTER TABLE cita DROP CONSTRAINT ck_cita_recurso_sin_solape")

    op.drop_index("ix_cita_asignacion_empleado_estado", table_name="cita_asignacion")
    op.drop_index("ix_cita_asignacion_cita", table_name="cita_asignacion")
    op.drop_table("cita_asignacion")

    op.drop_index("ix_cita_sucursal", table_name="cita")
    op.drop_index("ix_cita_empleado", table_name="cita")
    op.drop_table("cita")

    op.drop_index("ix_disponibilidad_recurso_recurso", table_name="disponibilidad_recurso")
    op.drop_table("disponibilidad_recurso")

    op.drop_index("ix_disponibilidad_excepcion_empleado_fecha", table_name="disponibilidad_excepcion")
    op.drop_table("disponibilidad_excepcion")

    op.drop_index("ix_disponibilidad_horario_empleado", table_name="disponibilidad_horario")
    op.drop_table("disponibilidad_horario")

    op.drop_table("empleado_servicio")

    op.drop_index("uq_recurso_nombre_activo", table_name="recurso")
    op.drop_table("recurso")

    op.drop_column("producto", "disponibilidad_cruzada_activa")
    op.drop_column("producto", "requiere_recurso")
    op.drop_column("producto", "tiempo_buffer_minutos")
    op.drop_column("producto", "duracion_minutos")
