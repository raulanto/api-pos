from sqlalchemy import inspect as sa_inspect

from app.modules.inventario.domain.entities import (
    Categoria, UnidadMedida, Producto, ProductoComponente, ProductoUnidad, ProductoImagen,
    InstanciaAbierta, Lote, ExistenciaLote, Existencia, MovimientoInventario,
)
from app.modules.inventario.domain.value_objects import (
    TipoProducto, TipoMovimiento, TipoMagnitud, EstadoInstancia,
)
from app.modules.inventario.infrastructure.persistence.orm_models import (
    CategoriaORM, UnidadMedidaORM, ProductoORM, ProductoComponenteORM, ProductoUnidadORM,
    ProductoImagenORM, InstanciaAbiertaORM, LoteORM, ExistenciaLoteORM, ExistenciaORM,
    MovimientoInventarioORM,
)


"""
    Transforma un lote ORM <-> entidad de dominio.
"""
def to_domain_lote(orm: LoteORM) -> Lote:
    return Lote(
        id=orm.id,
        producto_id=orm.producto_id,
        codigo_lote=orm.codigo_lote,
        fecha_caducidad=orm.fecha_caducidad,
        costo=orm.costo,
        proveedor=orm.proveedor,
        activo=orm.activo,
        created_at=orm.created_at,
    )


def to_orm_lote(entidad: Lote) -> LoteORM:
    return LoteORM(
        id=entidad.id,
        producto_id=entidad.producto_id,
        codigo_lote=entidad.codigo_lote,
        fecha_caducidad=entidad.fecha_caducidad,
        costo=entidad.costo,
        proveedor=entidad.proveedor,
        activo=entidad.activo,
    )


def to_domain_existencia_lote(
    orm: ExistenciaLoteORM, includes: frozenset[str] = frozenset()
) -> ExistenciaLote:
    el = ExistenciaLote(
        id=orm.id,
        producto_id=orm.producto_id,
        sucursal_id=orm.sucursal_id,
        lote_id=orm.lote_id,
        cantidad=orm.cantidad,
        updated_at=orm.updated_at,
    )
    if "lote" in includes:
        el.lote = to_domain_lote(orm.lote)
    return el


"""
    Transforma una unidad de medida (catálogo) ORM <-> entidad de dominio.
"""
def to_domain_unidad_medida(orm: UnidadMedidaORM) -> UnidadMedida:
    return UnidadMedida(
        id=orm.id,
        codigo=orm.codigo,
        nombre=orm.nombre,
        tipo_magnitud=TipoMagnitud(orm.tipo_magnitud),
        decimales=int(orm.decimales),
        activo=orm.activo,
        created_at=orm.created_at,
    )


def to_orm_unidad_medida(entidad: UnidadMedida) -> UnidadMedidaORM:
    return UnidadMedidaORM(
        id=entidad.id,
        codigo=entidad.codigo,
        nombre=entidad.nombre,
        tipo_magnitud=entidad.tipo_magnitud.value,
        decimales=entidad.decimales,
        activo=entidad.activo,
    )

"""
    Mappers para transformar entidades de dominio a ORM y viceversa.
    
    - Entidad -> ORM: Para guardar en base de datos.
    - ORM -> Entidad: Para devolver datos al servicio/API.
    @params:
    - orm: Modelo ORM.
    - entidad: Entidad de dominio.
    
    @returns:
    - Categoria
    - CategoriaORM
    - Producto
    - ProductoORM
    - Existencia
    - ExistenciaORM
    - MovimientoInventario
    - MovimientoInventarioORM
"""
def to_domain_categoria(orm: CategoriaORM, includes: frozenset[str] = frozenset()) -> Categoria:
    categoria = Categoria(
        id=orm.id,
        nombre=orm.nombre,
        categoria_padre_id=orm.categoria_padre_id,
        activo=orm.activo
    )
    if "padre" in includes:
        categoria.padre = orm.padre
    return categoria

"""
    Transforma una categoría ORM a una entidad de dominio.
    @params:
    - orm: Modelo ORM.
    @returns:
    - Categoria
"""
def to_orm_categoria(entidad: Categoria) -> CategoriaORM:
    return CategoriaORM(
        id=entidad.id,
        nombre=entidad.nombre,
        categoria_padre_id=entidad.categoria_padre_id,
        activo=entidad.activo
    )

"""
    Transforma un producto ORM a una entidad de dominio.
    @params:
    - orm: Modelo ORM.
    @returns:
    - Producto
"""
def to_domain_producto(orm: ProductoORM, includes: frozenset[str] = frozenset()) -> Producto:
    producto = Producto(
        id=orm.id,
        sku=orm.sku,
        codigo_barras=orm.codigo_barras,
        nombre=orm.nombre,
        descripcion=orm.descripcion,
        categoria_id=orm.categoria_id,
        unidad_medida=orm.unidad_medida,
        precio_venta=orm.precio_venta,
        costo=orm.costo,
        impuesto_tasa=orm.impuesto_tasa,
        tipo=TipoProducto(orm.tipo),
        permite_stock_negativo=orm.permite_stock_negativo,
        activo=orm.activo,
        created_at=orm.created_at,
        unidad_medida_id=orm.unidad_medida_id,
        permite_venta_fraccionada=orm.permite_venta_fraccionada,
        incremento_minimo_venta=orm.incremento_minimo_venta,
        requiere_lote=orm.requiere_lote,
        rastrea_instancia_abierta=orm.rastrea_instancia_abierta,
        instancia_capacidad_default=orm.instancia_capacidad_default,
        precio_incluye_impuesto=orm.precio_incluye_impuesto,
        precio_mayoreo=orm.precio_mayoreo,
        cantidad_minima_mayoreo=orm.cantidad_minima_mayoreo,
        es_sobre_pedido=orm.es_sobre_pedido,
        monedero_pct=orm.monedero_pct,
        monedero_monto=orm.monedero_monto,
        # Siempre presente: no depende de `includes` (ver `_opts_producto`,
        # que carga `imagen_principal` incondicionalmente).
        imagen_principal=to_domain_imagen(orm.imagen_principal) if orm.imagen_principal else None,
    )
    if "categoria" in includes:
        producto.categoria = orm.categoria
    if "existencias" in includes:
        producto.existencias = list(orm.existencias)
    if "componentes" in includes:
        # Sólo las líneas de la receta; el producto de cada componente se
        # consulta con GET /productos/{kit}/componentes?include=producto.
        producto.componentes = [to_domain_componente(c) for c in orm.componentes]
    if "unidades" in includes:
        producto.unidades = [
            to_domain_unidad(u) for u in orm.unidades if u.activo
        ]
    if "imagenes" in includes:
        producto.imagenes = [to_domain_imagen(i) for i in orm.imagenes]
    return producto


"""
    Transforma una imagen de catálogo ORM <-> entidad de dominio.
"""
def to_domain_imagen(orm: ProductoImagenORM) -> ProductoImagen:
    # Imagen propia (S3): `url` y `thumbnail_url` se derivan prefirmadas al leer.
    # Imagen externa: `url` es el valor guardado; no hay miniatura.
    url = orm.url
    thumbnail_url = None
    if orm.object_key:
        from app.core.aws import presign_get_url
        from app.modules.inventario.application.ports.almacen_imagenes import (
            AlmacenImagenes,
        )
        url = presign_get_url(orm.object_key)
        thumbnail_url = presign_get_url(AlmacenImagenes.key_miniatura(orm.object_key))
    return ProductoImagen(
        id=orm.id,
        producto_id=orm.producto_id,
        producto_unidad_id=orm.producto_unidad_id,
        url=url,
        object_key=orm.object_key,
        content_type=orm.content_type,
        alt_texto=orm.alt_texto,
        orden=orm.orden,
        es_principal=orm.es_principal,
        created_at=orm.created_at,
        thumbnail_url=thumbnail_url,
    )


def to_orm_imagen(entidad: ProductoImagen) -> ProductoImagenORM:
    return ProductoImagenORM(
        id=entidad.id,
        producto_id=entidad.producto_id,
        producto_unidad_id=entidad.producto_unidad_id,
        url=entidad.url,
        object_key=entidad.object_key,
        content_type=entidad.content_type,
        alt_texto=entidad.alt_texto,
        orden=entidad.orden,
        es_principal=entidad.es_principal,
    )


"""
    Transforma una presentación (producto_unidad) ORM a entidad de dominio.
    `imagen_principal` sólo se mapea si el repo la trajo cargada (`?include=unidades`);
    si no, la relación queda `lazy="raise"` y no se toca.
"""
def to_domain_unidad(orm: ProductoUnidadORM) -> ProductoUnidad:
    img = None
    if "imagen_principal" not in sa_inspect(orm).unloaded and orm.imagen_principal:
        img = to_domain_imagen(orm.imagen_principal)
    return ProductoUnidad(
        id=orm.id,
        producto_id=orm.producto_id,
        nombre=orm.nombre,
        unidad_medida=orm.unidad_medida,
        factor=orm.factor,
        precio_venta=orm.precio_venta,
        codigo_barras=orm.codigo_barras,
        activo=orm.activo,
        created_at=orm.created_at,
        monedero_pct=orm.monedero_pct,
        monedero_monto=orm.monedero_monto,
        imagen_principal=img,
    )


"""
    Transforma una línea kit/componente ORM a entidad de dominio.
    @params:
    - orm: Modelo ORM.
    - includes: {"producto"} para embeber el producto componente.
    @returns:
    - ProductoComponente
"""
def to_domain_componente(
    orm: ProductoComponenteORM, includes: frozenset[str] = frozenset()
) -> ProductoComponente:
    comp = ProductoComponente(
        producto_kit_id=orm.producto_kit_id,
        producto_componente_id=orm.producto_componente_id,
        cantidad=orm.cantidad,
    )
    if "producto" in includes:
        comp.producto = orm.producto
    return comp

"""
    Transforma un producto de dominio a ORM.
    @params:
    - entidad: Entidad de dominio.
    @returns:
    - ProductoORM
"""
def to_orm_producto(entidad: Producto) -> ProductoORM:
    return ProductoORM(
        id=entidad.id,
        sku=entidad.sku,
        codigo_barras=entidad.codigo_barras,
        nombre=entidad.nombre,
        descripcion=entidad.descripcion,
        categoria_id=entidad.categoria_id,
        unidad_medida=entidad.unidad_medida,
        unidad_medida_id=entidad.unidad_medida_id,
        precio_venta=entidad.precio_venta,
        costo=entidad.costo,
        impuesto_tasa=entidad.impuesto_tasa,
        tipo=entidad.tipo.value,
        permite_stock_negativo=entidad.permite_stock_negativo,
        permite_venta_fraccionada=entidad.permite_venta_fraccionada,
        incremento_minimo_venta=entidad.incremento_minimo_venta,
        requiere_lote=entidad.requiere_lote,
        rastrea_instancia_abierta=entidad.rastrea_instancia_abierta,
        instancia_capacidad_default=entidad.instancia_capacidad_default,
        precio_incluye_impuesto=entidad.precio_incluye_impuesto,
        precio_mayoreo=entidad.precio_mayoreo,
        cantidad_minima_mayoreo=entidad.cantidad_minima_mayoreo,
        es_sobre_pedido=entidad.es_sobre_pedido,
        monedero_pct=entidad.monedero_pct,
        monedero_monto=entidad.monedero_monto,
        activo=entidad.activo
    )


"""
    Transforma una instancia abierta ORM <-> entidad de dominio.
"""
def to_domain_instancia(orm: InstanciaAbiertaORM) -> InstanciaAbierta:
    return InstanciaAbierta(
        id=orm.id,
        producto_id=orm.producto_id,
        sucursal_id=orm.sucursal_id,
        producto_unidad_id=orm.producto_unidad_id,
        lote_id=orm.lote_id,
        capacidad_inicial=orm.capacidad_inicial,
        saldo=orm.saldo,
        estado=EstadoInstancia(orm.estado),
        abierta_por=orm.abierta_por,
        abierta_at=orm.abierta_at,
        cerrada_at=orm.cerrada_at,
        motivo_cierre=orm.motivo_cierre,
        created_at=orm.created_at,
    )


def to_orm_instancia(entidad: InstanciaAbierta) -> InstanciaAbiertaORM:
    return InstanciaAbiertaORM(
        id=entidad.id,
        producto_id=entidad.producto_id,
        sucursal_id=entidad.sucursal_id,
        producto_unidad_id=entidad.producto_unidad_id,
        lote_id=entidad.lote_id,
        capacidad_inicial=entidad.capacidad_inicial,
        saldo=entidad.saldo,
        estado=entidad.estado.value,
        abierta_por=entidad.abierta_por,
        abierta_at=entidad.abierta_at,
        cerrada_at=entidad.cerrada_at,
        motivo_cierre=entidad.motivo_cierre,
    )

"""
    Transforma una existencia ORM a una entidad de dominio.
    @params:
    - orm: Modelo ORM.
    @returns:
    - Existencia
"""
def to_domain_existencia(orm: ExistenciaORM, includes: frozenset[str] = frozenset()) -> Existencia:
    existencia = Existencia(
        id=orm.id,
        producto_id=orm.producto_id,
        sucursal_id=orm.sucursal_id,
        cantidad=orm.cantidad,
        stock_minimo=orm.stock_minimo,
        stock_maximo=orm.stock_maximo,
        updated_at=orm.updated_at
    )
    if "producto" in includes:
        existencia.producto = orm.producto
    return existencia

"""
    Transforma una existencia de dominio a ORM.
    @params:
    - entidad: Entidad de dominio.
    @returns:
    - ExistenciaORM
"""
def to_orm_existencia(entidad: Existencia) -> ExistenciaORM:
    return ExistenciaORM(
        id=entidad.id,
        producto_id=entidad.producto_id,
        sucursal_id=entidad.sucursal_id,
        cantidad=entidad.cantidad,
        stock_minimo=entidad.stock_minimo,
        stock_maximo=entidad.stock_maximo
    )

"""
    Transforma un movimiento ORM a una entidad de dominio.
    @params:
    - orm: Modelo ORM.
    @returns:
    - MovimientoInventario
"""
def to_domain_movimiento(
    orm: MovimientoInventarioORM, includes: frozenset[str] = frozenset()
) -> MovimientoInventario:
    mov = MovimientoInventario(
        id=orm.id,
        producto_id=orm.producto_id,
        sucursal_id=orm.sucursal_id,
        tipo=TipoMovimiento(orm.tipo),
        cantidad=orm.cantidad,
        costo_unitario=orm.costo_unitario,
        referencia_tipo=orm.referencia_tipo,
        referencia_id=orm.referencia_id,
        usuario_id=orm.usuario_id,
        motivo=orm.motivo,
        created_at=orm.created_at,
        unidad_capturada_id=orm.unidad_capturada_id,
        cantidad_capturada=orm.cantidad_capturada,
        lote_id=orm.lote_id,
        instancia_abierta_id=orm.instancia_abierta_id,
    )
    if "producto" in includes:
        mov.producto = orm.producto
    if "usuario" in includes:
        mov.usuario = orm.usuario
    return mov

"""
    Transforma un movimiento de dominio a ORM.
    @params:
    - entidad: Entidad de dominio.
    @returns:
    - MovimientoInventarioORM
"""
def to_orm_movimiento(entidad: MovimientoInventario) -> MovimientoInventarioORM:
    return MovimientoInventarioORM(
        id=entidad.id,
        producto_id=entidad.producto_id,
        sucursal_id=entidad.sucursal_id,
        tipo=entidad.tipo.value,
        cantidad=entidad.cantidad,
        costo_unitario=entidad.costo_unitario,
        referencia_tipo=entidad.referencia_tipo,
        referencia_id=entidad.referencia_id,
        usuario_id=entidad.usuario_id,
        motivo=entidad.motivo,
        unidad_capturada_id=entidad.unidad_capturada_id,
        cantidad_capturada=entidad.cantidad_capturada,
        lote_id=entidad.lote_id,
        instancia_abierta_id=entidad.instancia_abierta_id,
    )
