from app.modules.agenda.domain.entities import (
    Recurso, EmpleadoServicio, HorarioBase, ExcepcionDisponibilidad, HorarioRecurso,
    Cita, CitaAsignacion,
)
from app.modules.agenda.domain.value_objects import EstadoCita, EstadoAsignacion, TipoExcepcion
from app.modules.agenda.infrastructure.persistence.orm_models import (
    RecursoORM, EmpleadoServicioORM, DisponibilidadHorarioORM, DisponibilidadExcepcionORM,
    DisponibilidadRecursoORM, CitaORM, CitaAsignacionORM,
)


def to_domain_recurso(orm: RecursoORM) -> Recurso:
    return Recurso(
        id=orm.id, sucursal_id=orm.sucursal_id, nombre=orm.nombre,
        tipo=orm.tipo, activo=orm.activo, created_at=orm.created_at,
    )


def to_orm_recurso(entidad: Recurso) -> RecursoORM:
    return RecursoORM(
        id=entidad.id, sucursal_id=entidad.sucursal_id, nombre=entidad.nombre,
        tipo=entidad.tipo, activo=entidad.activo,
    )


def to_domain_empleado_servicio(orm: EmpleadoServicioORM) -> EmpleadoServicio:
    return EmpleadoServicio(
        id=orm.id, empleado_id=orm.empleado_id, servicio_id=orm.servicio_id,
        activo=orm.activo, created_at=orm.created_at,
    )


def to_domain_horario(orm: DisponibilidadHorarioORM) -> HorarioBase:
    return HorarioBase(
        id=orm.id, empleado_id=orm.empleado_id, sucursal_id=orm.sucursal_id,
        dia_semana=orm.dia_semana, hora_inicio=orm.hora_inicio, hora_fin=orm.hora_fin,
        created_at=orm.created_at,
    )


def to_orm_horario(entidad: HorarioBase) -> DisponibilidadHorarioORM:
    return DisponibilidadHorarioORM(
        id=entidad.id, empleado_id=entidad.empleado_id, sucursal_id=entidad.sucursal_id,
        dia_semana=entidad.dia_semana, hora_inicio=entidad.hora_inicio, hora_fin=entidad.hora_fin,
    )


def to_domain_excepcion(orm: DisponibilidadExcepcionORM) -> ExcepcionDisponibilidad:
    return ExcepcionDisponibilidad(
        id=orm.id, empleado_id=orm.empleado_id, fecha=orm.fecha, tipo=TipoExcepcion(orm.tipo),
        hora_inicio=orm.hora_inicio, hora_fin=orm.hora_fin, motivo=orm.motivo,
        created_at=orm.created_at,
    )


def to_orm_excepcion(entidad: ExcepcionDisponibilidad) -> DisponibilidadExcepcionORM:
    return DisponibilidadExcepcionORM(
        id=entidad.id, empleado_id=entidad.empleado_id, fecha=entidad.fecha,
        tipo=entidad.tipo.value, hora_inicio=entidad.hora_inicio, hora_fin=entidad.hora_fin,
        motivo=entidad.motivo,
    )


def to_domain_horario_recurso(orm: DisponibilidadRecursoORM) -> HorarioRecurso:
    return HorarioRecurso(
        id=orm.id, recurso_id=orm.recurso_id, dia_semana=orm.dia_semana,
        hora_inicio=orm.hora_inicio, hora_fin=orm.hora_fin, created_at=orm.created_at,
    )


def to_orm_horario_recurso(entidad: HorarioRecurso) -> DisponibilidadRecursoORM:
    return DisponibilidadRecursoORM(
        id=entidad.id, recurso_id=entidad.recurso_id, dia_semana=entidad.dia_semana,
        hora_inicio=entidad.hora_inicio, hora_fin=entidad.hora_fin,
    )


def to_domain_asignacion(orm: CitaAsignacionORM) -> CitaAsignacion:
    return CitaAsignacion(
        id=orm.id, cita_id=orm.cita_id, empleado_id=orm.empleado_id,
        estado=EstadoAsignacion(orm.estado), fecha_oferta=orm.fecha_oferta,
        fecha_respuesta=orm.fecha_respuesta,
    )


def to_orm_asignacion(entidad: CitaAsignacion) -> CitaAsignacionORM:
    return CitaAsignacionORM(
        id=entidad.id, cita_id=entidad.cita_id, empleado_id=entidad.empleado_id,
        estado=entidad.estado.value, fecha_oferta=entidad.fecha_oferta,
        fecha_respuesta=entidad.fecha_respuesta,
    )


def to_domain_cita(orm: CitaORM, includes: frozenset[str] = frozenset()) -> Cita:
    cita = Cita(
        id=orm.id, servicio_id=orm.servicio_id, sucursal_id=orm.sucursal_id,
        fecha_hora_inicio=orm.fecha_hora_inicio, fecha_hora_fin=orm.fecha_hora_fin,
        estado=EstadoCita(orm.estado), creado_por_usuario_id=orm.creado_por_usuario_id,
        cliente_id=orm.cliente_id, recurso_id=orm.recurso_id, empleado_id=orm.empleado_id,
        disponibilidad_cruzada=orm.disponibilidad_cruzada,
        politica_cancelacion_horas=orm.politica_cancelacion_horas,
        penalizacion_cancelacion=orm.penalizacion_cancelacion,
        motivo_cancelacion=orm.motivo_cancelacion, venta_detalle_id=orm.venta_detalle_id,
        created_at=orm.created_at,
        asignaciones=[to_domain_asignacion(a) for a in orm.asignaciones],
    )
    if "cliente" in includes:
        cita.cliente = orm.cliente
    if "empleado" in includes:
        cita.empleado = orm.empleado
    return cita


def to_orm_cita(entidad: Cita) -> CitaORM:
    orm = CitaORM(
        id=entidad.id, servicio_id=entidad.servicio_id, sucursal_id=entidad.sucursal_id,
        fecha_hora_inicio=entidad.fecha_hora_inicio, fecha_hora_fin=entidad.fecha_hora_fin,
        estado=entidad.estado.value, creado_por_usuario_id=entidad.creado_por_usuario_id,
        cliente_id=entidad.cliente_id, recurso_id=entidad.recurso_id,
        empleado_id=entidad.empleado_id, disponibilidad_cruzada=entidad.disponibilidad_cruzada,
        politica_cancelacion_horas=entidad.politica_cancelacion_horas,
        penalizacion_cancelacion=entidad.penalizacion_cancelacion,
        motivo_cancelacion=entidad.motivo_cancelacion, venta_detalle_id=entidad.venta_detalle_id,
        created_at=entidad.created_at,
    )
    orm.asignaciones = [to_orm_asignacion(a) for a in entidad.asignaciones]
    return orm
