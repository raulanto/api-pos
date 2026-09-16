from decimal import Decimal

from app.modules.ventas.domain.value_objects import MetodoPago
from app.modules.pedidos.domain.entities import Pedido, DetallePedido, PedidoPago
from app.modules.pedidos.domain.value_objects import (
    TipoPedido, CanalPedido, EstadoPedido, EstadoEntrega,
)
from app.modules.pedidos.infrastructure.persistence.orm_models import (
    PedidoORM, DetallePedidoORM, PedidoPagoORM,
)


def _det_to_orm(l: DetallePedido) -> DetallePedidoORM:
    return DetallePedidoORM(
        id=l.id, pedido_id=l.pedido_id, producto_id=l.producto_id,
        cantidad=l.cantidad, precio_unitario=l.precio_unitario,
        descuento_linea=l.descuento_linea, impuesto_tasa=l.impuesto_tasa,
        producto_unidad_id=l.producto_unidad_id,
        cantidad_en_unidad_base=l.cantidad_en_unidad_base,
        promo_id=l.promo_id, promo_etiqueta=l.promo_etiqueta,
        promo_descuento=l.promo_descuento,
        es_servicio=l.es_servicio, asignado_a=l.asignado_a,
    )


def _pago_to_orm(p: PedidoPago) -> PedidoPagoORM:
    return PedidoPagoORM(
        id=p.id, pedido_id=p.pedido_id, monto=p.monto,
        metodo_pago=p.metodo_pago.value, referencia=p.referencia,
        reembolsado=p.reembolsado, created_at=p.created_at,
    )


def to_orm_pedido(e: Pedido) -> PedidoORM:
    orm = PedidoORM(
        id=e.id, sucursal_id=e.sucursal_id, usuario_id=e.usuario_id,
        cliente_id=e.cliente_id, tipo=e.tipo.value, canal=e.canal.value,
        estado=e.estado.value,
        estado_entrega=e.estado_entrega.value if e.estado_entrega else None,
        telefono=e.telefono, descuento_total=e.descuento_total,
        motivo_descuento=e.motivo_descuento,
        codigo_cupon=e.codigo_cupon, cliente_segmento=e.cliente_segmento,
        notas=e.notas, fecha_promesa=e.fecha_promesa,
        direccion_texto=e.direccion_texto, referencia_direccion=e.referencia_direccion,
        repartidor_id=e.repartidor_id, entrega_fallo_motivo=e.entrega_fallo_motivo,
        despachado_en=e.despachado_en, entregado_en=e.entregado_en,
        venta_id=e.venta_id, idempotency_key=e.idempotency_key,
        created_at=e.created_at,
    )
    orm.lineas = [_det_to_orm(l) for l in e.lineas]
    orm.pagos = [_pago_to_orm(p) for p in e.pagos]
    return orm


def to_domain_pedido(orm: PedidoORM) -> Pedido:
    return Pedido(
        id=orm.id, sucursal_id=orm.sucursal_id, usuario_id=orm.usuario_id,
        tipo=TipoPedido(orm.tipo), canal=CanalPedido(orm.canal),
        estado=EstadoPedido(orm.estado),
        estado_entrega=EstadoEntrega(orm.estado_entrega) if orm.estado_entrega else None,
        cliente_id=orm.cliente_id, telefono=orm.telefono,
        descuento_total=orm.descuento_total or Decimal("0"),
        motivo_descuento=orm.motivo_descuento,
        codigo_cupon=orm.codigo_cupon, cliente_segmento=orm.cliente_segmento,
        notas=orm.notas, fecha_promesa=orm.fecha_promesa,
        direccion_texto=orm.direccion_texto,
        referencia_direccion=orm.referencia_direccion,
        repartidor_id=orm.repartidor_id, entrega_fallo_motivo=orm.entrega_fallo_motivo,
        despachado_en=orm.despachado_en, entregado_en=orm.entregado_en,
        venta_id=orm.venta_id, idempotency_key=orm.idempotency_key,
        created_at=orm.created_at,
        lineas=[
            DetallePedido(
                id=l.id, pedido_id=l.pedido_id, producto_id=l.producto_id,
                cantidad=l.cantidad, precio_unitario=l.precio_unitario,
                descuento_linea=l.descuento_linea, impuesto_tasa=l.impuesto_tasa,
                producto_unidad_id=l.producto_unidad_id,
                cantidad_en_unidad_base=l.cantidad_en_unidad_base,
                promo_id=l.promo_id, promo_etiqueta=l.promo_etiqueta,
                promo_descuento=l.promo_descuento,
                es_servicio=l.es_servicio, asignado_a=l.asignado_a,
            ) for l in sorted(orm.lineas, key=lambda x: str(x.id))
        ],
        pagos=[
            PedidoPago(
                id=p.id, pedido_id=p.pedido_id, monto=p.monto,
                metodo_pago=MetodoPago(p.metodo_pago), referencia=p.referencia,
                reembolsado=p.reembolsado, created_at=p.created_at,
            ) for p in sorted(orm.pagos, key=lambda x: x.created_at)
        ],
    )
