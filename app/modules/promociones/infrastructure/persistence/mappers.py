from app.modules.promociones.domain.entities import (
    Promocion, PromocionObjetivo, TipoPromocion,
)
from app.modules.promociones.infrastructure.persistence.orm_models import (
    PromocionORM, PromocionObjetivoORM,
)


def to_domain_objetivo(orm: PromocionObjetivoORM) -> PromocionObjetivo:
    return PromocionObjetivo(
        id=orm.id,
        promocion_id=orm.promocion_id,
        producto_id=orm.producto_id,
        producto_unidad_id=orm.producto_unidad_id,
    )


def to_domain_promocion(orm: PromocionORM) -> Promocion:
    return Promocion(
        id=orm.id,
        nombre=orm.nombre,
        tipo=TipoPromocion(orm.tipo),
        activo=orm.activo,
        prioridad=orm.prioridad,
        sucursal_id=orm.sucursal_id,
        vigente_desde=orm.vigente_desde,
        vigente_hasta=orm.vigente_hasta,
        nxm_lleva=orm.nxm_lleva,
        nxm_paga=orm.nxm_paga,
        descuento_pct=orm.descuento_pct,
        precio_fijo=orm.precio_fijo,
        cantidad_minima=orm.cantidad_minima,
        created_at=orm.created_at,
        updated_at=orm.updated_at,
        objetivos=[to_domain_objetivo(o) for o in orm.objetivos],
    )


def to_orm_objetivo(entidad: PromocionObjetivo) -> PromocionObjetivoORM:
    return PromocionObjetivoORM(
        id=entidad.id,
        promocion_id=entidad.promocion_id,
        producto_id=entidad.producto_id,
        producto_unidad_id=entidad.producto_unidad_id,
    )


def to_orm_promocion(entidad: Promocion) -> PromocionORM:
    orm = PromocionORM(
        id=entidad.id,
        nombre=entidad.nombre,
        tipo=entidad.tipo.value,
        activo=entidad.activo,
        prioridad=entidad.prioridad,
        sucursal_id=entidad.sucursal_id,
        vigente_desde=entidad.vigente_desde,
        vigente_hasta=entidad.vigente_hasta,
        nxm_lleva=entidad.nxm_lleva,
        nxm_paga=entidad.nxm_paga,
        descuento_pct=entidad.descuento_pct,
        precio_fijo=entidad.precio_fijo,
        cantidad_minima=entidad.cantidad_minima,
    )
    orm.objetivos = [to_orm_objetivo(o) for o in entidad.objetivos]
    return orm
