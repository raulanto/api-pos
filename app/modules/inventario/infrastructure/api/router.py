from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import (
    require_permission, UsuarioAutenticado, sucursal_scope, verificar_alcance_sucursal,
)
from app.modules.inventario.application.dtos import (
    FiltroProductos, FiltroMovimientos, Paginacion,
)
from app.modules.inventario.domain.value_objects import TipoMovimiento
from app.modules.inventario.domain import exceptions as exc
from app.modules.inventario.infrastructure.api.schemas import (
    CrearCategoriaRequest, ActualizarCategoriaRequest, CategoriaResponse,
    CrearProductoRequest, ActualizarProductoRequest, ProductoResponse, ProductosPaginados,
    ExistenciaResponse, ConfigurarUmbralesRequest,
    AplicarMovimientoRequest, TransferenciaRequest, MovimientoResponse, MovimientosPaginados,
)
from app.modules.inventario.infrastructure.persistence.repositories_impl import (
    SqlAlchemyCategoriaRepository, SqlAlchemyProductoRepository,
    SqlAlchemyExistenciaRepository, SqlAlchemyMovimientoRepository,
)
from app.modules.inventario.infrastructure.adapters.event_port_impl import EventPortImpl
from app.modules.inventario.application.use_cases.crear_categoria import (
    CrearCategoriaUseCase, CrearCategoriaInput,
)
from app.modules.inventario.application.use_cases.gestionar_categorias import (
    ListarCategoriasUseCase, ObtenerCategoriaUseCase,
    ActualizarCategoriaUseCase, ActualizarCategoriaInput, DesactivarCategoriaUseCase,
)
from app.modules.inventario.application.use_cases.crear_producto import (
    CrearProductoUseCase, CrearProductoInput,
)
from app.modules.inventario.application.use_cases.gestionar_productos import (
    ListarProductosUseCase, ObtenerProductoUseCase, BuscarProductoPorCodigoBarrasUseCase,
    ActualizarProductoUseCase, ActualizarProductoInput, DesactivarProductoUseCase,
)
from app.modules.inventario.application.use_cases.consultar_existencias import (
    ConsultarExistenciasUseCase, ListarBajoStockUseCase,
    ConfigurarUmbralesUseCase, ConfigurarUmbralesInput,
)
from app.modules.inventario.application.use_cases.listar_movimientos import (
    ListarMovimientosUseCase, ObtenerMovimientoUseCase,
)
from app.modules.inventario.application.use_cases.aplicar_movimiento import (
    AplicarMovimientoUseCase, AplicarMovimientoInput,
)
from app.modules.inventario.application.use_cases.transferir_stock import (
    TransferirStockUseCase, TransferirStockInput,
)

router = APIRouter()

# --------------------------------------------------------------------------- #
# Mapeo de excepciones de dominio -> HTTP
# --------------------------------------------------------------------------- #
_NOT_FOUND = (
    exc.ProductoNoEncontrado, exc.CategoriaNoEncontrada, exc.ExistenciaNoEncontrada,
    exc.MovimientoNoEncontrado,
)
_CONFLICT = (exc.CategoriaConProductosActivos, exc.ProductoConStockActivo)
_BAD_REQUEST = (
    exc.SkuDuplicado, exc.CodigoBarrasDuplicado, exc.StockInsuficiente,
    exc.AjusteSinCantidadFinal, exc.TransferenciaInvalida, exc.JerarquiaCategoriaInvalida,
    exc.ProductoInactivo, ValueError,
)


def _traducir(error: Exception) -> HTTPException:
    if isinstance(error, _NOT_FOUND):
        return HTTPException(status.HTTP_404_NOT_FOUND, detail=str(error))
    if isinstance(error, _CONFLICT):
        return HTTPException(status.HTTP_409_CONFLICT, detail=str(error))
    if isinstance(error, _BAD_REQUEST):
        return HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(error))
    raise error


# `CategoriaNoEncontrada` como FK inexistente en un create => 400, no 404.
def _traducir_create(error: Exception) -> HTTPException:
    if isinstance(error, exc.CategoriaNoEncontrada):
        return HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(error))
    return _traducir(error)


# --------------------------------------------------------------------------- #
# Fábricas de repositorios / casos de uso
# --------------------------------------------------------------------------- #
def _cat_repo(db):
    return SqlAlchemyCategoriaRepository(db)

def _prod_repo(db):
    return SqlAlchemyProductoRepository(db)

def _exist_repo(db):
    return SqlAlchemyExistenciaRepository(db)

def _mov_repo(db):
    return SqlAlchemyMovimientoRepository(db)


# ========================================================================== #
# CATEGORÍAS
# ========================================================================== #
@router.post("/categorias", response_model=CategoriaResponse, status_code=status.HTTP_201_CREATED)
async def crear_categoria(
    body: CrearCategoriaRequest,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("inventario.crear")),
):
    try:
        categoria = await CrearCategoriaUseCase(_cat_repo(db)).ejecutar(
            CrearCategoriaInput(nombre=body.nombre, categoria_padre_id=body.categoria_padre_id)
        )
    except Exception as e:
        raise _traducir_create(e)
    return categoria


@router.get("/categorias", response_model=list[CategoriaResponse])
async def listar_categorias(
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("inventario.leer")),
    activo: bool | None = Query(default=None),
    categoria_padre_id: UUID | None = Query(default=None),
):
    return await ListarCategoriasUseCase(_cat_repo(db)).ejecutar(
        activo=activo, categoria_padre_id=categoria_padre_id
    )


@router.get("/categorias/{categoria_id}", response_model=CategoriaResponse)
async def obtener_categoria(
    categoria_id: UUID,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("inventario.leer")),
):
    try:
        return await ObtenerCategoriaUseCase(_cat_repo(db)).ejecutar(categoria_id)
    except Exception as e:
        raise _traducir(e)


@router.patch("/categorias/{categoria_id}", response_model=CategoriaResponse)
async def actualizar_categoria(
    categoria_id: UUID,
    body: ActualizarCategoriaRequest,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("inventario.editar")),
):
    try:
        categoria = await ActualizarCategoriaUseCase(_cat_repo(db)).ejecutar(
            ActualizarCategoriaInput(
                categoria_id=categoria_id,
                nombre=body.nombre,
                categoria_padre_id=body.categoria_padre_id,
                cambiar_padre=body.cambiar_padre,
            )
        )
    except Exception as e:
        raise _traducir(e)
    return categoria


@router.patch("/categorias/{categoria_id}/desactivar", response_model=CategoriaResponse)
async def desactivar_categoria(
    categoria_id: UUID,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("inventario.editar")),
):
    try:
        categoria = await DesactivarCategoriaUseCase(_cat_repo(db)).ejecutar(categoria_id)
    except Exception as e:
        raise _traducir(e)
    return categoria


# ========================================================================== #
# PRODUCTOS
# ========================================================================== #
@router.post("/productos", response_model=ProductoResponse, status_code=status.HTTP_201_CREATED)
async def crear_producto(
    body: CrearProductoRequest,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("inventario.crear")),
):
    try:
        producto = await CrearProductoUseCase(_prod_repo(db), _cat_repo(db)).ejecutar(
            CrearProductoInput(
                sku=body.sku, nombre=body.nombre, categoria_id=body.categoria_id,
                unidad_medida=body.unidad_medida, precio_venta=body.precio_venta,
                costo=body.costo, impuesto_tasa=body.impuesto_tasa,
                permite_stock_negativo=body.permite_stock_negativo,
                codigo_barras=body.codigo_barras, descripcion=body.descripcion,
            )
        )
    except Exception as e:
        raise _traducir_create(e)
    return producto


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
    pagina = await ListarProductosUseCase(_prod_repo(db)).ejecutar(
        FiltroProductos(categoria_id=categoria_id, activo=activo, busqueda=q),
        Paginacion(limit=limit, offset=offset),
    )
    return ProductosPaginados(items=pagina.items, total=pagina.total, limit=limit, offset=offset)


@router.get("/productos/buscar", response_model=ProductoResponse)
async def buscar_producto_por_codigo_barras(
    codigo_barras: str = Query(min_length=1),
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("inventario.leer")),
):
    try:
        return await BuscarProductoPorCodigoBarrasUseCase(_prod_repo(db)).ejecutar(codigo_barras)
    except Exception as e:
        raise _traducir(e)


@router.get("/productos/{producto_id}", response_model=ProductoResponse)
async def obtener_producto(
    producto_id: UUID,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("inventario.leer")),
):
    try:
        return await ObtenerProductoUseCase(_prod_repo(db)).ejecutar(producto_id)
    except Exception as e:
        raise _traducir(e)


@router.patch("/productos/{producto_id}", response_model=ProductoResponse)
async def actualizar_producto(
    producto_id: UUID,
    body: ActualizarProductoRequest,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("inventario.editar")),
):
    try:
        producto = await ActualizarProductoUseCase(_prod_repo(db), _cat_repo(db)).ejecutar(
            ActualizarProductoInput(
                producto_id=producto_id,
                nombre=body.nombre, descripcion=body.descripcion, categoria_id=body.categoria_id,
                unidad_medida=body.unidad_medida, precio_venta=body.precio_venta, costo=body.costo,
                impuesto_tasa=body.impuesto_tasa, permite_stock_negativo=body.permite_stock_negativo,
                codigo_barras=body.codigo_barras, cambiar_codigo_barras=body.cambiar_codigo_barras,
            )
        )
    except Exception as e:
        raise _traducir(e)
    return producto


@router.patch("/productos/{producto_id}/desactivar", response_model=ProductoResponse)
async def desactivar_producto(
    producto_id: UUID,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("inventario.editar")),
    confirmar_con_stock: bool = Query(default=False),
):
    try:
        producto = await DesactivarProductoUseCase(_prod_repo(db), _exist_repo(db)).ejecutar(
            producto_id, confirmar_con_stock=confirmar_con_stock
        )
    except Exception as e:
        raise _traducir(e)
    return producto


# ========================================================================== #
# EXISTENCIAS
# ========================================================================== #
@router.get("/existencias", response_model=list[ExistenciaResponse])
async def listar_existencias(
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("inventario.leer")),
    producto_id: UUID | None = Query(default=None),
    sucursal_id: UUID | None = Query(default=None),
):
    efectivo = _sucursal_efectiva(actual, sucursal_id)
    return await ConsultarExistenciasUseCase(_exist_repo(db)).ejecutar(
        producto_id=producto_id, sucursal_id=efectivo
    )


@router.get("/existencias/bajo-stock", response_model=list[ExistenciaResponse])
async def listar_bajo_stock(
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("inventario.leer")),
    sucursal_id: UUID | None = Query(default=None),
):
    efectivo = _sucursal_efectiva(actual, sucursal_id)
    return await ListarBajoStockUseCase(_exist_repo(db)).ejecutar(sucursal_id=efectivo)


@router.patch(
    "/existencias/{producto_id}/{sucursal_id}/umbrales",
    response_model=ExistenciaResponse,
)
async def configurar_umbrales(
    producto_id: UUID,
    sucursal_id: UUID,
    body: ConfigurarUmbralesRequest,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("inventario.editar")),
):
    verificar_alcance_sucursal(actual, sucursal_id)
    try:
        existencia = await ConfigurarUmbralesUseCase(_exist_repo(db), _prod_repo(db)).ejecutar(
            ConfigurarUmbralesInput(
                producto_id=producto_id, sucursal_id=sucursal_id,
                stock_minimo=body.stock_minimo, stock_maximo=body.stock_maximo,
            )
        )
    except Exception as e:
        raise _traducir(e)
    return existencia


# ========================================================================== #
# MOVIMIENTOS
# ========================================================================== #
@router.post("/movimientos", status_code=status.HTTP_201_CREATED)
async def aplicar_movimiento(
    body: AplicarMovimientoRequest,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("inventario.movimiento")),
):
    if not actual.sucursal_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="El usuario no tiene una sucursal asignada")
    if body.tipo == TipoMovimiento.TRANSFERENCIA:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Usá POST /movimientos/transferencia para transferencias entre sucursales.",
        )

    use_case = AplicarMovimientoUseCase(
        _prod_repo(db), _exist_repo(db), _mov_repo(db), EventPortImpl(db)
    )
    try:
        await use_case.ejecutar(AplicarMovimientoInput(
            producto_id=body.producto_id,
            sucursal_id=actual.sucursal_id,
            tipo=body.tipo,
            referencia_tipo=body.referencia_tipo,
            usuario_id=actual.id,
            cantidad=body.cantidad,
            cantidad_final=body.cantidad_final,
            referencia_id=body.referencia_id,
            costo_unitario=body.costo_unitario,
            motivo=body.motivo,
            stock_minimo=body.stock_minimo,
            stock_maximo=body.stock_maximo,
        ))
    except Exception as e:
        raise _traducir(e)
    return {"status": "ok"}


@router.post("/movimientos/transferencia", status_code=status.HTTP_201_CREATED)
async def transferir_stock(
    body: TransferenciaRequest,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("inventario.movimiento")),
):
    # Un usuario no global sólo puede sacar stock de su propia sucursal.
    verificar_alcance_sucursal(actual, body.sucursal_origen_id)

    use_case = TransferirStockUseCase(
        _prod_repo(db), _exist_repo(db), _mov_repo(db), EventPortImpl(db)
    )
    try:
        await use_case.ejecutar(TransferirStockInput(
            producto_id=body.producto_id,
            sucursal_origen_id=body.sucursal_origen_id,
            sucursal_destino_id=body.sucursal_destino_id,
            cantidad=body.cantidad,
            usuario_id=actual.id,
            referencia_id=body.referencia_id,
            costo_unitario=body.costo_unitario,
            motivo=body.motivo,
        ))
    except Exception as e:
        raise _traducir(e)
    return {"status": "ok"}


@router.get("/movimientos", response_model=MovimientosPaginados)
async def listar_movimientos(
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("inventario.leer")),
    producto_id: UUID | None = Query(default=None),
    sucursal_id: UUID | None = Query(default=None),
    tipo: TipoMovimiento | None = Query(default=None),
    desde: datetime | None = Query(default=None),
    hasta: datetime | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    efectivo = _sucursal_efectiva(actual, sucursal_id)
    pagina = await ListarMovimientosUseCase(_mov_repo(db)).ejecutar(
        FiltroMovimientos(
            producto_id=producto_id, sucursal_id=efectivo, tipo=tipo, desde=desde, hasta=hasta,
        ),
        Paginacion(limit=limit, offset=offset),
    )
    return MovimientosPaginados(items=pagina.items, total=pagina.total, limit=limit, offset=offset)


@router.get("/movimientos/{movimiento_id}", response_model=MovimientoResponse)
async def obtener_movimiento(
    movimiento_id: UUID,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("inventario.leer")),
):
    try:
        movimiento = await ObtenerMovimientoUseCase(_mov_repo(db)).ejecutar(movimiento_id)
    except Exception as e:
        raise _traducir(e)
    verificar_alcance_sucursal(actual, movimiento.sucursal_id)
    return movimiento


# --------------------------------------------------------------------------- #
def _sucursal_efectiva(actual: UsuarioAutenticado, pedida: UUID | None) -> UUID | None:
    """Sección 10/11: los roles no globales quedan atados a su sucursal.

    - rol global (admin/gerente): respeta el filtro pedido, o None => todas.
    - rol de sucursal: siempre su propia sucursal; si pide otra distinta => 403.
    """
    alcance = sucursal_scope(actual)  # None => global
    if alcance is None:
        return pedida
    if pedida is not None and pedida != alcance:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Fuera del alcance de su sucursal")
    return alcance
