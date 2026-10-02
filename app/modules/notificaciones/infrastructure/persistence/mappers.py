from app.modules.notificaciones.domain.entities import Notificacion
from app.modules.notificaciones.infrastructure.persistence.orm_models import NotificacionORM


def to_domain(orm: NotificacionORM) -> Notificacion:
    return Notificacion(
        id=orm.id,
        usuario_id=orm.usuario_id,
        sucursal_id=orm.sucursal_id,
        modulo=orm.modulo,
        tipo=orm.tipo,
        titulo=orm.titulo,
        mensaje=orm.mensaje,
        leida=orm.leida,
        fecha_leida=orm.fecha_leida,
        entidad=orm.entidad,
        entidad_id=orm.entidad_id,
        datos=orm.datos or {},
        created_at=orm.created_at,
    )


def to_orm(domain: Notificacion) -> NotificacionORM:
    return NotificacionORM(
        id=domain.id,
        usuario_id=domain.usuario_id,
        sucursal_id=domain.sucursal_id,
        modulo=domain.modulo,
        tipo=domain.tipo,
        titulo=domain.titulo,
        mensaje=domain.mensaje,
        leida=domain.leida,
        fecha_leida=domain.fecha_leida,
        entidad=domain.entidad,
        entidad_id=domain.entidad_id,
        datos=domain.datos,
        created_at=domain.created_at,
    )
