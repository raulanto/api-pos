from app.modules.proveedores.domain.entities import (
    Proveedor, ProductoProveedor, PedidoProveedor, PedidoProveedorLinea,
    RecepcionProveedor, RecepcionProveedorLinea, DevolucionProveedor, DevolucionProveedorLinea,
)
from app.modules.proveedores.domain.value_objects import (
    TipoPersona, CondicionesPago, EstadoPedidoProveedor, EstadoRecepcion,
    MotivoDefecto, AccionDefecto, EstadoDevolucionProveedor, ResultadoDevolucion,
    TipoResolucionDevolucion,
)
from app.modules.proveedores.infrastructure.persistence.orm_models import (
    ProveedorORM, ProductoProveedorORM, PedidoProveedorORM, PedidoProveedorLineaORM,
    RecepcionProveedorORM, RecepcionProveedorLineaORM, DevolucionProveedorORM,
    DevolucionProveedorLineaORM,
)

_DIRECCION_CAMPOS = (
    "direccion_calle", "direccion_numero", "direccion_colonia", "direccion_ciudad",
    "direccion_estado", "direccion_codigo_postal",
)


def to_domain_proveedor(orm: ProveedorORM) -> Proveedor:
    return Proveedor(
        id=orm.id, codigo=orm.codigo, razon_social=orm.razon_social,
        tipo_persona=TipoPersona(orm.tipo_persona),
        condiciones_pago=CondicionesPago(orm.condiciones_pago),
        dias_credito=orm.dias_credito, nombre_comercial=orm.nombre_comercial,
        rfc=orm.rfc, moneda=orm.moneda, contacto_principal=orm.contacto_principal,
        telefono=orm.telefono, email=orm.email,
        **{c: getattr(orm, c) for c in _DIRECCION_CAMPOS},
        activo=orm.activo, notas=orm.notas, created_at=orm.created_at,
        updated_at=orm.updated_at,
    )


def to_orm_proveedor(entidad: Proveedor) -> ProveedorORM:
    return ProveedorORM(
        id=entidad.id, codigo=entidad.codigo, razon_social=entidad.razon_social,
        tipo_persona=entidad.tipo_persona.value, condiciones_pago=entidad.condiciones_pago.value,
        dias_credito=entidad.dias_credito, nombre_comercial=entidad.nombre_comercial,
        rfc=entidad.rfc, moneda=entidad.moneda, contacto_principal=entidad.contacto_principal,
        telefono=entidad.telefono, email=entidad.email,
        **{c: getattr(entidad, c) for c in _DIRECCION_CAMPOS},
        activo=entidad.activo, notas=entidad.notas,
    )


def to_domain_producto_proveedor(orm: ProductoProveedorORM) -> ProductoProveedor:
    return ProductoProveedor(
        id=orm.id, producto_id=orm.producto_id, proveedor_id=orm.proveedor_id,
        precio_compra=orm.precio_compra, tiempo_entrega_dias=orm.tiempo_entrega_dias,
        stock_minimo=orm.stock_minimo, cantidad_reorden=orm.cantidad_reorden,
        codigo_proveedor=orm.codigo_proveedor, stock_maximo=orm.stock_maximo,
        es_proveedor_principal=orm.es_proveedor_principal, activo=orm.activo,
        created_at=orm.created_at,
    )


def to_orm_producto_proveedor(entidad: ProductoProveedor) -> ProductoProveedorORM:
    return ProductoProveedorORM(
        id=entidad.id, producto_id=entidad.producto_id, proveedor_id=entidad.proveedor_id,
        precio_compra=entidad.precio_compra, tiempo_entrega_dias=entidad.tiempo_entrega_dias,
        stock_minimo=entidad.stock_minimo, cantidad_reorden=entidad.cantidad_reorden,
        codigo_proveedor=entidad.codigo_proveedor, stock_maximo=entidad.stock_maximo,
        es_proveedor_principal=entidad.es_proveedor_principal, activo=entidad.activo,
    )


def to_domain_pedido_linea(orm: PedidoProveedorLineaORM) -> PedidoProveedorLinea:
    return PedidoProveedorLinea(
        id=orm.id, pedido_id=orm.pedido_id, producto_id=orm.producto_id,
        cantidad_solicitada=orm.cantidad_solicitada, precio_unitario=orm.precio_unitario,
        cantidad_recibida=orm.cantidad_recibida,
    )


def to_orm_pedido_linea(entidad: PedidoProveedorLinea) -> PedidoProveedorLineaORM:
    return PedidoProveedorLineaORM(
        id=entidad.id, pedido_id=entidad.pedido_id, producto_id=entidad.producto_id,
        cantidad_solicitada=entidad.cantidad_solicitada, precio_unitario=entidad.precio_unitario,
        cantidad_recibida=entidad.cantidad_recibida,
    )


def to_domain_pedido(orm: PedidoProveedorORM) -> PedidoProveedor:
    return PedidoProveedor(
        id=orm.id, proveedor_id=orm.proveedor_id, sucursal_id=orm.sucursal_id,
        estado=EstadoPedidoProveedor(orm.estado), fecha_pedido=orm.fecha_pedido,
        generado_automaticamente=orm.generado_automaticamente, generado_por=orm.generado_por,
        confirmado_por=orm.confirmado_por, fecha_estimada_entrega=orm.fecha_estimada_entrega,
        notas=orm.notas, created_at=orm.created_at,
        lineas=[to_domain_pedido_linea(l) for l in orm.lineas],
    )


def to_orm_pedido(entidad: PedidoProveedor) -> PedidoProveedorORM:
    orm = PedidoProveedorORM(
        id=entidad.id, proveedor_id=entidad.proveedor_id, sucursal_id=entidad.sucursal_id,
        estado=entidad.estado.value, generado_automaticamente=entidad.generado_automaticamente,
        generado_por=entidad.generado_por, confirmado_por=entidad.confirmado_por,
        fecha_pedido=entidad.fecha_pedido, fecha_estimada_entrega=entidad.fecha_estimada_entrega,
        notas=entidad.notas, created_at=entidad.created_at,
    )
    orm.lineas = [to_orm_pedido_linea(l) for l in entidad.lineas]
    return orm


def to_domain_recepcion_linea(orm: RecepcionProveedorLineaORM) -> RecepcionProveedorLinea:
    return RecepcionProveedorLinea(
        id=orm.id, recepcion_id=orm.recepcion_id, producto_id=orm.producto_id,
        cantidad_recibida_buena=orm.cantidad_recibida_buena,
        cantidad_defectuosa=orm.cantidad_defectuosa, cantidad_esperada=orm.cantidad_esperada,
        motivo_defecto=MotivoDefecto(orm.motivo_defecto) if orm.motivo_defecto else None,
        accion_defecto=AccionDefecto(orm.accion_defecto) if orm.accion_defecto else None,
        fotos_evidencia_keys=list(orm.fotos_evidencia_keys or []), notas=orm.notas,
    )


def to_orm_recepcion_linea(entidad: RecepcionProveedorLinea) -> RecepcionProveedorLineaORM:
    return RecepcionProveedorLineaORM(
        id=entidad.id, recepcion_id=entidad.recepcion_id, producto_id=entidad.producto_id,
        cantidad_recibida_buena=entidad.cantidad_recibida_buena,
        cantidad_defectuosa=entidad.cantidad_defectuosa, cantidad_esperada=entidad.cantidad_esperada,
        motivo_defecto=entidad.motivo_defecto.value if entidad.motivo_defecto else None,
        accion_defecto=entidad.accion_defecto.value if entidad.accion_defecto else None,
        fotos_evidencia_keys=entidad.fotos_evidencia_keys or None, notas=entidad.notas,
    )


def to_domain_recepcion(orm: RecepcionProveedorORM) -> RecepcionProveedor:
    return RecepcionProveedor(
        id=orm.id, proveedor_id=orm.proveedor_id, sucursal_id=orm.sucursal_id,
        recibido_por=orm.recibido_por, fecha_recepcion=orm.fecha_recepcion,
        estado=EstadoRecepcion(orm.estado),
        lineas=[to_domain_recepcion_linea(l) for l in orm.lineas],
        pedido_id=orm.pedido_id, numero_factura=orm.numero_factura,
        numero_remision=orm.numero_remision, transportista=orm.transportista,
        notas=orm.notas, created_at=orm.created_at,
    )


def to_orm_recepcion(entidad: RecepcionProveedor) -> RecepcionProveedorORM:
    orm = RecepcionProveedorORM(
        id=entidad.id, proveedor_id=entidad.proveedor_id, sucursal_id=entidad.sucursal_id,
        recibido_por=entidad.recibido_por, fecha_recepcion=entidad.fecha_recepcion,
        estado=entidad.estado.value, pedido_id=entidad.pedido_id,
        numero_factura=entidad.numero_factura, numero_remision=entidad.numero_remision,
        transportista=entidad.transportista, notas=entidad.notas, created_at=entidad.created_at,
    )
    orm.lineas = [to_orm_recepcion_linea(l) for l in entidad.lineas]
    return orm


def to_domain_devolucion_linea(orm: DevolucionProveedorLineaORM) -> DevolucionProveedorLinea:
    return DevolucionProveedorLinea(
        id=orm.id, devolucion_id=orm.devolucion_id,
        recepcion_detalle_id=orm.recepcion_detalle_id, producto_id=orm.producto_id,
        cantidad=orm.cantidad,
    )


def to_orm_devolucion_linea(entidad: DevolucionProveedorLinea) -> DevolucionProveedorLineaORM:
    return DevolucionProveedorLineaORM(
        id=entidad.id, devolucion_id=entidad.devolucion_id,
        recepcion_detalle_id=entidad.recepcion_detalle_id, producto_id=entidad.producto_id,
        cantidad=entidad.cantidad,
    )


def to_domain_devolucion(orm: DevolucionProveedorORM) -> DevolucionProveedor:
    return DevolucionProveedor(
        id=orm.id, proveedor_id=orm.proveedor_id, recepcion_id=orm.recepcion_id,
        creado_por=orm.creado_por, estado=EstadoDevolucionProveedor(orm.estado),
        lineas=[to_domain_devolucion_linea(l) for l in orm.lineas],
        resultado=ResultadoDevolucion(orm.resultado) if orm.resultado else None,
        tipo_resolucion=(
            TipoResolucionDevolucion(orm.tipo_resolucion) if orm.tipo_resolucion else None
        ),
        fecha_envio=orm.fecha_envio, fecha_cierre=orm.fecha_cierre, notas=orm.notas,
        created_at=orm.created_at,
    )


def to_orm_devolucion(entidad: DevolucionProveedor) -> DevolucionProveedorORM:
    orm = DevolucionProveedorORM(
        id=entidad.id, proveedor_id=entidad.proveedor_id, recepcion_id=entidad.recepcion_id,
        creado_por=entidad.creado_por, estado=entidad.estado.value,
        resultado=entidad.resultado.value if entidad.resultado else None,
        tipo_resolucion=entidad.tipo_resolucion.value if entidad.tipo_resolucion else None,
        fecha_envio=entidad.fecha_envio, fecha_cierre=entidad.fecha_cierre, notas=entidad.notas,
        created_at=entidad.created_at,
    )
    orm.lineas = [to_orm_devolucion_linea(l) for l in entidad.lineas]
    return orm
