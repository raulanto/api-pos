from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import (
    require_permission, UsuarioAutenticado, verificar_alcance_sucursal,
)
from app.shared.responses import (
    ApiResponse, EnvelopeRoute, PageParams, Sort,
    page_params, make_sort_dependency, make_include_dependency, ok, page_response,
)
from app.shared.filtering import active_filters
from app.modules.inventario.application.dtos import FiltroProductos
from app.modules.inventario.domain.value_objects import TipoProducto
from app.modules.inventario.application.use_cases.crear_producto import (
    CrearProductoUseCase, CrearProductoInput,
)
from app.modules.inventario.application.use_cases.gestionar_productos import (
    ListarProductosUseCase, ObtenerProductoUseCase, BuscarProductoPorCodigoBarrasUseCase,
    ActualizarProductoUseCase, ActualizarProductoInput, DesactivarProductoUseCase,
    ReactivarProductoUseCase, ProductoKpisUseCase,
)
from app.modules.inventario.infrastructure.api.schemas import (
    CrearProductoRequest, ActualizarProductoRequest, ProductoResponse, ProductoKpisResponse,
)
from .common import prod_repo, cat_repo, exist_repo, traducir, traducir_create

router = APIRouter(route_class=EnvelopeRoute)

_ORDEN_PRODUCTOS = make_sort_dependency(
    {"nombre", "sku", "precio_venta", "created_at"}, "nombre:asc"
)
_INC_PRODUCTOS = make_include_dependency({"categoria", "existencias"})

"""
    Endpoint para crear un producto.

    @param body: Cuerpo de la solicitud.
    @param db: Sesión de la base de datos.
    @param actual: Usuario autenticado.
    @return: Instancia de la clase ProductoResponse.
"""
@router.post(
    "/productos", response_model=ApiResponse[ProductoResponse],
    status_code=status.HTTP_201_CREATED,
)
async def crear_producto(
    body: CrearProductoRequest,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("inventario.crear")),
):
    try:
        producto = await CrearProductoUseCase(prod_repo(db), cat_repo(db)).ejecutar(
            CrearProductoInput(
                sku=body.sku, nombre=body.nombre, categoria_id=body.categoria_id,
                unidad_medida=body.unidad_medida, precio_venta=body.precio_venta,
                costo=body.costo, impuesto_tasa=body.impuesto_tasa,
                permite_stock_negativo=body.permite_stock_negativo,
                codigo_barras=body.codigo_barras, descripcion=body.descripcion,
            )
        )
    except Exception as e:
        raise traducir_create(e)
    return ok(producto)

"""
    Endpoint para listar productos.

    @param db: Sesión de la base de datos.
    @param actual: Usuario autenticado.
    @param categoria_id: ID de la categoría.
    @param activo: Indica si el producto está activo.
    @param q: Término de búsqueda.
    @param limit: Límite de resultados.
    @param offset: Desplazamiento de resultados.
    @return: ApiResponse[list[ProductoResponse]]
"""
@router.get("/productos", response_model=ApiResponse[list[ProductoResponse]])
async def listar_productos(
    request: Request,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("inventario.leer")),
    categoria_id: list[UUID] | None = Query(default=None),
    activo: bool | None = Query(default=None),
    q: str | None = Query(default=None, description="Busca en nombre, sku y código de barras"),
    sucursal_id: list[UUID] | None = Query(
        default=None, description="Sólo productos con existencia en esa(s) sucursal(es)"
    ),
    paginacion: PageParams = Depends(page_params),
    orden: Sort = Depends(_ORDEN_PRODUCTOS),
    include: frozenset[str] = Depends(_INC_PRODUCTOS),
):
    for s in sucursal_id or ():
        verificar_alcance_sucursal(actual, s)  # rol de sucursal no consulta otras
    filtro = FiltroProductos(
        categoria_id=categoria_id, activo=activo, busqueda=q, sucursal_id=sucursal_id,
    )
    pagina = await ListarProductosUseCase(prod_repo(db)).ejecutar(filtro, paginacion, orden, include)
    return page_response(
        request, pagina, paginacion, sort=orden, filters=active_filters(filtro),
    )


"""
    Endpoint para buscar un producto por código de barras.

    @param codigo_barras: Código de barras del producto.
    @param db: Sesión de la base de datos.
    @param actual: Usuario autenticado.
    @return: Instancia de la clase ProductoResponse.
"""
@router.get("/productos/buscar", response_model=ApiResponse[ProductoResponse])
async def buscar_producto_por_codigo_barras(
    codigo_barras: str = Query(min_length=1),
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("inventario.leer")),
    include: frozenset[str] = Depends(_INC_PRODUCTOS),
):
    try:
        producto = await BuscarProductoPorCodigoBarrasUseCase(prod_repo(db)).ejecutar(codigo_barras)
        if include:
            producto = await ObtenerProductoUseCase(prod_repo(db)).ejecutar(producto.id, include)
    except Exception as e:
        raise traducir(e)
    return ok(producto)


"""
    Endpoint de KPIs del catálogo + valuación de stock.

    Acepta los mismos filtros que GET /productos (categoria_id, activo, q,
    sucursal_id) más: tipo, permite_stock_negativo, con_codigo_barras,
    precio_min/max, costo_min/max, solo_bajo_stock. Los KPIs de stock/valor se
    calculan sobre las existencias de las `sucursal_id` indicadas (todas si no
    se pasa ninguna).
"""
@router.get("/productos/kpis", response_model=ApiResponse[ProductoKpisResponse])
async def kpis_productos(
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("inventario.leer")),
    categoria_id: list[UUID] | None = Query(default=None),
    activo: bool | None = Query(default=None),
    q: str | None = Query(default=None, description="Busca en nombre, sku y código de barras"),
    sucursal_id: list[UUID] | None = Query(
        default=None, description="Acota stock/valor a esa(s) sucursal(es)"
    ),
    tipo: TipoProducto | None = Query(default=None),
    permite_stock_negativo: bool | None = Query(default=None),
    con_codigo_barras: bool | None = Query(
        default=None, description="true=solo con código de barras, false=solo sin"
    ),
    precio_min: Decimal | None = Query(default=None, ge=0),
    precio_max: Decimal | None = Query(default=None, ge=0),
    costo_min: Decimal | None = Query(default=None, ge=0),
    costo_max: Decimal | None = Query(default=None, ge=0),
    solo_bajo_stock: bool = Query(default=False),
):
    for s in sucursal_id or ():
        verificar_alcance_sucursal(actual, s)  # rol de sucursal no consulta otras
    filtro = FiltroProductos(
        categoria_id=categoria_id, activo=activo, busqueda=q, sucursal_id=sucursal_id,
        tipo=tipo, permite_stock_negativo=permite_stock_negativo,
        con_codigo_barras=con_codigo_barras,
        precio_min=precio_min, precio_max=precio_max,
        costo_min=costo_min, costo_max=costo_max, solo_bajo_stock=solo_bajo_stock,
    )
    kpis = await ProductoKpisUseCase(prod_repo(db)).ejecutar(filtro)
    return ok(kpis)


"""
    Endpoint para obtener un producto.

    @param producto_id: ID del producto.
    @param db: Sesión de la base de datos.
    @param actual: Usuario autenticado.
    @return: Instancia de la clase ProductoResponse.
"""
@router.get("/productos/{producto_id}", response_model=ApiResponse[ProductoResponse])
async def obtener_producto(
    producto_id: UUID,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("inventario.leer")),
    include: frozenset[str] = Depends(_INC_PRODUCTOS),
):
    try:
        producto = await ObtenerProductoUseCase(prod_repo(db)).ejecutar(producto_id, include)
    except Exception as e:
        raise traducir(e)
    return ok(producto)


"""
    Endpoint para actualizar un producto.

    @param producto_id: ID del producto.
    @param body: Cuerpo de la solicitud.
    @param db: Sesión de la base de datos.
    @param actual: Usuario autenticado.
    @return: Instancia de la clase ProductoResponse.
"""
@router.patch("/productos/{producto_id}", response_model=ApiResponse[ProductoResponse])
async def actualizar_producto(
    producto_id: UUID,
    body: ActualizarProductoRequest,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("inventario.editar")),
):
    try:
        producto = await ActualizarProductoUseCase(prod_repo(db), cat_repo(db)).ejecutar(
            ActualizarProductoInput(
                producto_id=producto_id,
                sku=body.sku,
                nombre=body.nombre, descripcion=body.descripcion, categoria_id=body.categoria_id,
                unidad_medida=body.unidad_medida, precio_venta=body.precio_venta, costo=body.costo,
                impuesto_tasa=body.impuesto_tasa, tipo=body.tipo,
                permite_stock_negativo=body.permite_stock_negativo,
                codigo_barras=body.codigo_barras, cambiar_codigo_barras=body.cambiar_codigo_barras,
                cambiar_descripcion=body.cambiar_descripcion,
            )
        )
    except Exception as e:
        raise traducir(e)
    return ok(producto)


"""
    Endpoint para desactivar un producto.

    @param producto_id: ID del producto.
    @param db: Sesión de la base de datos.
    @param actual: Usuario autenticado.
    @param confirmar_con_stock: Indica si se debe confirmar con stock.
    @return: Instancia de la clase ProductoResponse.
"""
@router.patch(
    "/productos/{producto_id}/desactivar", response_model=ApiResponse[ProductoResponse],
)
async def desactivar_producto(
    producto_id: UUID,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("inventario.editar")),
    confirmar_con_stock: bool = Query(default=False),
):
    try:
        producto = await DesactivarProductoUseCase(prod_repo(db), exist_repo(db)).ejecutar(
            producto_id, confirmar_con_stock=confirmar_con_stock
        )
    except Exception as e:
        raise traducir(e)
    return ok(producto)


"""
    Endpoint para reactivar un producto dado de baja.

    @param producto_id: ID del producto.
    @param db: Sesión de la base de datos.
    @param actual: Usuario autenticado.
    @return: Instancia de la clase ProductoResponse.
"""
@router.patch(
    "/productos/{producto_id}/activar", response_model=ApiResponse[ProductoResponse],
)
async def activar_producto(
    producto_id: UUID,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("inventario.editar")),
):
    try:
        producto = await ReactivarProductoUseCase(prod_repo(db)).ejecutar(producto_id)
    except Exception as e:
        raise traducir(e)
    return ok(producto)
