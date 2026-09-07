from app.modules.ventas.domain.entities import (
    Venta, DetalleVenta, Pago, CajaTurno, Devolucion, DevolucionLinea,
)
from app.modules.ventas.domain.value_objects import (
    EstadoVenta, MetodoPago, MetodoDevolucion,
)
from app.modules.ventas.infrastructure.persistence.orm_models import (
    VentaORM, DetalleVentaORM, PagoORM, CajaTurnoORM, DevolucionORM, DevolucionLineaORM,
)

def to_domain_caja_turno(orm: CajaTurnoORM) -> CajaTurno:
    return CajaTurno(
        id=orm.id,
        sucursal_id=orm.sucursal_id,
        usuario_id=orm.usuario_id,
        saldo_inicial=orm.saldo_inicial,
        estado=orm.estado,
        abierto_en=orm.abierto_en,
        cerrado_en=orm.cerrado_en,
        saldo_final_declarado=orm.saldo_final_declarado,
        diferencia=orm.diferencia,
    )


def to_orm_caja_turno(entidad: CajaTurno) -> CajaTurnoORM:
    return CajaTurnoORM(
        id=entidad.id,
        sucursal_id=entidad.sucursal_id,
        usuario_id=entidad.usuario_id,
        saldo_inicial=entidad.saldo_inicial,
        estado=entidad.estado,
        abierto_en=entidad.abierto_en,
        cerrado_en=entidad.cerrado_en,
        saldo_final_declarado=entidad.saldo_final_declarado,
        diferencia=entidad.diferencia,
    )

def to_orm_venta(entidad: Venta) -> VentaORM:
    orm = VentaORM(
        id=entidad.id,
        sucursal_id=entidad.sucursal_id,
        caja_turno_id=entidad.caja_turno_id,
        usuario_id=entidad.usuario_id,
        cliente_id=entidad.cliente_id,
        estado=entidad.estado.value,
        descuento_total=entidad.descuento_total,
        idempotency_key=entidad.idempotency_key,
        created_at=entidad.created_at
    )
    orm.lineas = [
        DetalleVentaORM(
            id=l.id,
            venta_id=l.venta_id,
            producto_id=l.producto_id,
            cantidad=l.cantidad,
            precio_unitario=l.precio_unitario,
            descuento_linea=l.descuento_linea,
            impuesto_tasa=l.impuesto_tasa,
            producto_unidad_id=l.producto_unidad_id,
            cantidad_en_unidad_base=l.cantidad_en_unidad_base,
            promo_id=l.promo_id,
            promo_descuento=l.promo_descuento,
            promo_etiqueta=l.promo_etiqueta,
            cantidad_devuelta=l.cantidad_devuelta,
        ) for l in entidad.lineas
    ]
    orm.pagos = [
        PagoORM(
            id=p.id,
            venta_id=p.venta_id,
            monto=p.monto,
            metodo_pago=p.metodo_pago.value,
            monto_recibido=p.monto_recibido,
            created_at=p.created_at
        ) for p in entidad.pagos
    ]
    return orm

def to_domain_venta(orm: VentaORM, includes: frozenset[str] = frozenset()) -> Venta:
    venta = Venta(
        id=orm.id,
        sucursal_id=orm.sucursal_id,
        caja_turno_id=orm.caja_turno_id,
        usuario_id=orm.usuario_id,
        cliente_id=orm.cliente_id,
        estado=EstadoVenta(orm.estado),
        descuento_total=orm.descuento_total,
        idempotency_key=orm.idempotency_key,
        created_at=orm.created_at,
        lineas=[
            DetalleVenta(
                id=l.id,
                venta_id=l.venta_id,
                producto_id=l.producto_id,
                cantidad=l.cantidad,
                precio_unitario=l.precio_unitario,
                descuento_linea=l.descuento_linea,
                impuesto_tasa=l.impuesto_tasa,
                producto_unidad_id=l.producto_unidad_id,
                cantidad_en_unidad_base=l.cantidad_en_unidad_base,
                promo_id=l.promo_id,
                promo_etiqueta=l.promo_etiqueta,
                promo_descuento=l.promo_descuento,
                cantidad_devuelta=l.cantidad_devuelta,
            ) for l in orm.lineas
        ],
        pagos=[
            Pago(
                id=p.id,
                venta_id=p.venta_id,
                monto=p.monto,
                metodo_pago=MetodoPago(p.metodo_pago),
                monto_recibido=p.monto_recibido,
                created_at=p.created_at
            ) for p in orm.pagos
        ]
    )
    if "cliente" in includes:
        venta.cliente = orm.cliente
    if "usuario" in includes:
        venta.usuario = orm.usuario
    if "caja_turno" in includes:
        venta.caja_turno = orm.caja_turno
    return venta


def to_orm_devolucion(entidad: Devolucion) -> DevolucionORM:
    orm = DevolucionORM(
        id=entidad.id,
        venta_id=entidad.venta_id,
        caja_turno_id=entidad.caja_turno_id,
        usuario_id=entidad.usuario_id,
        motivo=entidad.motivo,
        monto_devuelto=entidad.monto_devuelto,
        metodo_devolucion=entidad.metodo_devolucion.value,
        idempotency_key=entidad.idempotency_key,
        created_at=entidad.created_at,
    )
    orm.lineas = [
        DevolucionLineaORM(
            id=l.id, devolucion_id=l.devolucion_id,
            detalle_venta_id=l.detalle_venta_id, cantidad=l.cantidad, monto=l.monto,
        ) for l in entidad.lineas
    ]
    return orm


def to_domain_devolucion(orm: DevolucionORM) -> Devolucion:
    return Devolucion(
        id=orm.id,
        venta_id=orm.venta_id,
        caja_turno_id=orm.caja_turno_id,
        usuario_id=orm.usuario_id,
        metodo_devolucion=MetodoDevolucion(orm.metodo_devolucion),
        monto_devuelto=orm.monto_devuelto,
        motivo=orm.motivo,
        idempotency_key=orm.idempotency_key,
        created_at=orm.created_at,
        lineas=[
            DevolucionLinea(
                id=l.id, devolucion_id=l.devolucion_id,
                detalle_venta_id=l.detalle_venta_id, cantidad=l.cantidad, monto=l.monto,
            ) for l in orm.lineas
        ],
    )
