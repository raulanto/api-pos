from app.modules.promociones.domain.entities import (
    Promocion, PromocionObjetivo, TipoPromocion,
)
from app.modules.promociones.infrastructure.persistence.orm_models import (
    PromocionORM, PromocionObjetivoORM, PromocionSucursalORM,
)


def to_domain_objetivo(orm: PromocionObjetivoORM) -> PromocionObjetivo:
    return PromocionObjetivo(
        id=orm.id,
        promocion_id=orm.promocion_id,
        producto_id=orm.producto_id,
        producto_unidad_id=orm.producto_unidad_id,
        categoria_id=orm.categoria_id,
    )


def to_domain_promocion(orm: PromocionORM) -> Promocion:
    return Promocion(
        id=orm.id,
        nombre=orm.nombre,
        tipo=TipoPromocion(orm.tipo),
        activo=orm.activo,
        prioridad=orm.prioridad,
        combinable=orm.combinable,
        tope_descuento=orm.tope_descuento,
        monto_minimo_compra=orm.monto_minimo_compra,
        metodo_pago_requerido=orm.metodo_pago_requerido,
        cliente_segmento=orm.cliente_segmento,
        requiere_cupon=orm.requiere_cupon,
        sucursales=[s.sucursal_id for s in orm.sucursales],
        vigente_desde=orm.vigente_desde,
        vigente_hasta=orm.vigente_hasta,
        hora_desde=orm.hora_desde,
        hora_hasta=orm.hora_hasta,
        dias_semana=orm.dias_semana,
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
        categoria_id=entidad.categoria_id,
    )


def to_orm_promocion(entidad: Promocion) -> PromocionORM:
    orm = PromocionORM(
        id=entidad.id,
        nombre=entidad.nombre,
        tipo=entidad.tipo.value,
        activo=entidad.activo,
        prioridad=entidad.prioridad,
        combinable=entidad.combinable,
        tope_descuento=entidad.tope_descuento,
        monto_minimo_compra=entidad.monto_minimo_compra,
        metodo_pago_requerido=entidad.metodo_pago_requerido,
        cliente_segmento=entidad.cliente_segmento,
        requiere_cupon=entidad.requiere_cupon,
        vigente_desde=entidad.vigente_desde,
        vigente_hasta=entidad.vigente_hasta,
        hora_desde=entidad.hora_desde,
        hora_hasta=entidad.hora_hasta,
        dias_semana=entidad.dias_semana,
        nxm_lleva=entidad.nxm_lleva,
        nxm_paga=entidad.nxm_paga,
        descuento_pct=entidad.descuento_pct,
        precio_fijo=entidad.precio_fijo,
        cantidad_minima=entidad.cantidad_minima,
    )
    orm.objetivos = [to_orm_objetivo(o) for o in entidad.objetivos]
    orm.sucursales = [
        PromocionSucursalORM(promocion_id=entidad.id, sucursal_id=sid)
        for sid in entidad.sucursales
    ]
    return orm


from app.modules.promociones.domain.entities import Cupon, CuponUso  # noqa: E402
from app.modules.promociones.infrastructure.persistence.orm_models import (  # noqa: E402
    CuponORM, CuponUsoORM,
)


def to_domain_cupon(orm: CuponORM) -> Cupon:
    return Cupon(
        id=orm.id, codigo=orm.codigo, promocion_id=orm.promocion_id, activo=orm.activo,
        vigente_desde=orm.vigente_desde, vigente_hasta=orm.vigente_hasta,
        max_usos_total=orm.max_usos_total, max_usos_por_persona=orm.max_usos_por_persona,
        created_at=orm.created_at,
    )


def to_orm_cupon(entidad: Cupon) -> CuponORM:
    return CuponORM(
        id=entidad.id, codigo=entidad.codigo, promocion_id=entidad.promocion_id,
        activo=entidad.activo, vigente_desde=entidad.vigente_desde,
        vigente_hasta=entidad.vigente_hasta, max_usos_total=entidad.max_usos_total,
        max_usos_por_persona=entidad.max_usos_por_persona,
    )


def to_orm_cupon_uso(entidad: CuponUso) -> CuponUsoORM:
    return CuponUsoORM(
        id=entidad.id, cupon_id=entidad.cupon_id, venta_id=entidad.venta_id,
        telefono=entidad.telefono, cliente_id=entidad.cliente_id,
        monto_descontado=entidad.monto_descontado,
    )
