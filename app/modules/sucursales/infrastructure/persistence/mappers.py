from app.modules.sucursales.domain.entities import Sucursal, TipoSucursal
from app.modules.sucursales.infrastructure.persistence.orm_models import SucursalORM


def to_domain_sucursal(orm: SucursalORM) -> Sucursal:
    # La URL de la fachada se deriva prefirmada al leer (mismo patrón que
    # `to_domain_imagen` en inventario); nunca se persiste.
    imagen_fachada_url = None
    if orm.imagen_fachada_key:
        from app.core.aws import presign_get_url
        imagen_fachada_url = presign_get_url(orm.imagen_fachada_key)
    return Sucursal(
        id=orm.id,
        nombre=orm.nombre,
        direccion=orm.direccion,
        telefono=orm.telefono,
        activo=orm.activo,
        created_at=orm.created_at,
        tipo=TipoSucursal(orm.tipo),
        permite_ventas=orm.permite_ventas,
        codigo=orm.codigo,
        descripcion=orm.descripcion,
        imagen_fachada_key=orm.imagen_fachada_key,
        colonia=orm.colonia,
        ciudad=orm.ciudad,
        estado=orm.estado,
        codigo_postal=orm.codigo_postal,
        pais=orm.pais,
        latitud=orm.latitud,
        longitud=orm.longitud,
        email=orm.email,
        horario_apertura=orm.horario_apertura,
        horario_cierre=orm.horario_cierre,
        sucursal_padre_id=orm.sucursal_padre_id,
        updated_at=orm.updated_at,
        imagen_fachada_url=imagen_fachada_url,
    )


def to_orm_sucursal(entidad: Sucursal) -> SucursalORM:
    return SucursalORM(
        id=entidad.id,
        codigo=entidad.codigo,
        nombre=entidad.nombre,
        tipo=entidad.tipo.value,
        descripcion=entidad.descripcion,
        imagen_fachada_key=entidad.imagen_fachada_key,
        direccion=entidad.direccion,
        colonia=entidad.colonia,
        ciudad=entidad.ciudad,
        estado=entidad.estado,
        codigo_postal=entidad.codigo_postal,
        pais=entidad.pais,
        latitud=entidad.latitud,
        longitud=entidad.longitud,
        telefono=entidad.telefono,
        email=entidad.email,
        horario_apertura=entidad.horario_apertura,
        horario_cierre=entidad.horario_cierre,
        sucursal_padre_id=entidad.sucursal_padre_id,
        permite_ventas=entidad.permite_ventas,
        activo=entidad.activo,
    )
