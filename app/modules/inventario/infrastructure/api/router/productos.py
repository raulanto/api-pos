from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_permission, UsuarioAutenticado
from app.modules.inventario.application.dtos import FiltroProductos, Paginacion
from app.modules.inventario.application.use_cases.crear_producto import (
    CrearProductoUseCase, CrearProductoInput,
)
from app.modules.inventario.application.use_cases.gestionar_productos import (
    ListarProductosUseCase, ObtenerProductoUseCase, BuscarProductoPorCodigoBarrasUseCase,
    ActualizarProductoUseCase, ActualizarProductoInput, DesactivarProductoUseCase,
)
from app.modules.inventario.infrastructure.api.schemas import (
    CrearProductoRequest, ActualizarProductoRequest, ProductoResponse, ProductosPaginados,
)
from .common import prod_repo, cat_repo, exist_repo, traducir, traducir_create

router = APIRouter()

"""
    Endpoint para crear un producto.

    @param body: Cuerpo de la solicitud.
    @param db: Sesión de la base de datos.
    @param actual: Usuario autenticado.
    @return: Instancia de la clase ProductoResponse.
"""
@router.post("/productos", response_model=ProductoResponse, status_code=status.HTTP_201_CREATED)
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
    return producto

"""
    Endpoint para listar productos.

    @param db: Sesión de la base de datos.
    @param actual: Usuario autenticado.
    @param categoria_id: ID de la categoría.
    @param activo: Indica si el producto está activo.
    @param q: Término de búsqueda.
    @param limit: Límite de resultados.
    @param offset: Desplazamiento de resultados.
    @return: Instancia de la clase ProductosPaginados.
"""
@router.get("/productos", response_model=ProductosPaginados)
async def listar_productos(
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("inventario.leer")),
    categoria_id: UUID | None = Query(default=None),
    activo: bool | None = Query(default=None),
    q: str | None = Query(default=None, description="Busca en nombre, sku y código de barras"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    pagina = await ListarProductosUseCase(prod_repo(db)).ejecutar(
        FiltroProductos(categoria_id=categoria_id, activo=activo, busqueda=q),
        Paginacion(limit=limit, offset=offset),
    )
    return ProductosPaginados(items=pagina.items, total=pagina.total, limit=limit, offset=offset)


"""
    Endpoint para buscar un producto por código de barras.

    @param codigo_barras: Código de barras del producto.
    @param db: Sesión de la base de datos.
    @param actual: Usuario autenticado.
    @return: Instancia de la clase ProductoResponse.
"""
@router.get("/productos/buscar", response_model=ProductoResponse)
async def buscar_producto_por_codigo_barras(
    codigo_barras: str = Query(min_length=1),
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("inventario.leer")),
):
    try:
        return await BuscarProductoPorCodigoBarrasUseCase(prod_repo(db)).ejecutar(codigo_barras)
    except Exception as e:
        raise traducir(e)


"""
    Endpoint para obtener un producto.

    @param producto_id: ID del producto.
    @param db: Sesión de la base de datos.
    @param actual: Usuario autenticado.
    @return: Instancia de la clase ProductoResponse.
"""
@router.get("/productos/{producto_id}", response_model=ProductoResponse)
async def obtener_producto(
    producto_id: UUID,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("inventario.leer")),
):
    try:
        return await ObtenerProductoUseCase(prod_repo(db)).ejecutar(producto_id)
    except Exception as e:
        raise traducir(e)


"""
    Endpoint para actualizar un producto.

    @param producto_id: ID del producto.
    @param body: Cuerpo de la solicitud.
    @param db: Sesión de la base de datos.
    @param actual: Usuario autenticado.
    @return: Instancia de la clase ProductoResponse.
"""
@router.patch("/productos/{producto_id}", response_model=ProductoResponse)
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
                nombre=body.nombre, descripcion=body.descripcion, categoria_id=body.categoria_id,
                unidad_medida=body.unidad_medida, precio_venta=body.precio_venta, costo=body.costo,
                impuesto_tasa=body.impuesto_tasa, permite_stock_negativo=body.permite_stock_negativo,
                codigo_barras=body.codigo_barras, cambiar_codigo_barras=body.cambiar_codigo_barras,
            )
        )
    except Exception as e:
        raise traducir(e)
    return producto


"""
    Endpoint para desactivar un producto.

    @param producto_id: ID del producto.
    @param db: Sesión de la base de datos.
    @param actual: Usuario autenticado.
    @param confirmar_con_stock: Indica si se debe confirmar con stock.
    @return: Instancia de la clase ProductoResponse.
"""
@router.patch("/productos/{producto_id}/desactivar", response_model=ProductoResponse)
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
    return producto
