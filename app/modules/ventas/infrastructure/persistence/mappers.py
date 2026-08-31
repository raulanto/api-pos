from app.modules.ventas.domain.entities import Venta, DetalleVenta, Pago, CajaTurno
from app.modules.ventas.domain.value_objects import EstadoVenta, MetodoPago
from app.modules.ventas.infrastructure.persistence.orm_models import VentaORM, DetalleVentaORM, PagoORM, CajaTurnoORM

def to_domain_caja_turno(orm: CajaTurnoORM) -> CajaTurno:
    return CajaTurno(
        id=orm.id,
        sucursal_id=orm.sucursal_id,
        usuario_id=orm.usuario_id,
        saldo_inicial=orm.saldo_inicial,
        estado=orm.estado,
        abierto_en=orm.abierto_en,
        cerrado_en=orm.cerrado_en
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
            impuesto_tasa=l.impuesto_tasa
        ) for l in entidad.lineas
    ]
    orm.pagos = [
        PagoORM(
            id=p.id,
            venta_id=p.venta_id,
            monto=p.monto,
            metodo_pago=p.metodo_pago.value,
            created_at=p.created_at
        ) for p in entidad.pagos
    ]
    return orm

def to_domain_venta(orm: VentaORM) -> Venta:
    venta = Venta(
        id=orm.id,
        sucursal_id=orm.sucursal_id,
        caja_turno_id=orm.caja_turno_id,
        usuario_id=orm.usuario_id,
        cliente_id=orm.cliente_id,
        estado=EstadoVenta(orm.estado),
        descuento_total=orm.descuento_total,
        created_at=orm.created_at,
        lineas=[
            DetalleVenta(
                id=l.id,
                venta_id=l.venta_id,
                producto_id=l.producto_id,
                cantidad=l.cantidad,
                precio_unitario=l.precio_unitario,
                descuento_linea=l.descuento_linea,
                impuesto_tasa=l.impuesto_tasa
            ) for l in orm.lineas
        ],
        pagos=[
            Pago(
                id=p.id,
                venta_id=p.venta_id,
                monto=p.monto,
                metodo_pago=MetodoPago(p.metodo_pago),
                created_at=p.created_at
            ) for p in orm.pagos
        ]
    )
    return venta
