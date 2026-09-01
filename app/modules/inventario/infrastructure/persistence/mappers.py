from app.modules.inventario.domain.entities import Categoria, Producto, Existencia, MovimientoInventario
from app.modules.inventario.domain.value_objects import TipoProducto, TipoMovimiento
from app.modules.inventario.infrastructure.persistence.orm_models import CategoriaORM, ProductoORM, ExistenciaORM, MovimientoInventarioORM

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
        created_at=orm.created_at
    )
    if "categoria" in includes:
        producto.categoria = orm.categoria
    if "existencias" in includes:
        producto.existencias = list(orm.existencias)
    return producto

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
        precio_venta=entidad.precio_venta,
        costo=entidad.costo,
        impuesto_tasa=entidad.impuesto_tasa,
        tipo=entidad.tipo.value,
        permite_stock_negativo=entidad.permite_stock_negativo,
        activo=entidad.activo
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
        motivo=entidad.motivo
    )
