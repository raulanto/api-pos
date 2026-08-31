from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.modules.usuarios.domain.entities import Usuario
from app.modules.inventario.infrastructure.api.schemas import (
    CrearCategoriaRequest, CategoriaResponse,
    CrearProductoRequest, ProductoResponse,
    AplicarMovimientoRequest
)
from app.modules.inventario.application.use_cases.crear_categoria import CrearCategoriaUseCase, CrearCategoriaInput
from app.modules.inventario.application.use_cases.crear_producto import CrearProductoUseCase, CrearProductoInput
from app.modules.inventario.application.use_cases.aplicar_movimiento import AplicarMovimientoUseCase, AplicarMovimientoInput
from app.modules.inventario.infrastructure.persistence.repositories_impl import (
    SqlAlchemyCategoriaRepository,
    SqlAlchemyProductoRepository,
    SqlAlchemyExistenciaRepository,
    SqlAlchemyMovimientoRepository
)
from app.modules.inventario.domain.exceptions import CategoriaNoEncontrada, ProductoNoEncontrado, StockInsuficiente

router = APIRouter()

def get_crear_categoria_use_case(db: AsyncSession = Depends(get_db)) -> CrearCategoriaUseCase:
    return CrearCategoriaUseCase(SqlAlchemyCategoriaRepository(db))

def get_crear_producto_use_case(db: AsyncSession = Depends(get_db)) -> CrearProductoUseCase:
    return CrearProductoUseCase(
        producto_repo=SqlAlchemyProductoRepository(db),
        categoria_repo=SqlAlchemyCategoriaRepository(db)
    )

def get_aplicar_movimiento_use_case(db: AsyncSession = Depends(get_db)) -> AplicarMovimientoUseCase:
    return AplicarMovimientoUseCase(
        producto_repo=SqlAlchemyProductoRepository(db),
        existencia_repo=SqlAlchemyExistenciaRepository(db),
        movimiento_repo=SqlAlchemyMovimientoRepository(db)
    )

# Mock get_current_user dependency for compilation, ideally it should come from app.core.dependencies

@router.post("/categorias", response_model=CategoriaResponse, status_code=status.HTTP_201_CREATED)
async def crear_categoria(
    body: CrearCategoriaRequest,
    use_case: CrearCategoriaUseCase = Depends(get_crear_categoria_use_case),
    usuario_actual: Usuario = Depends(get_current_user)
):
    try:
        categoria = await use_case.ejecutar(CrearCategoriaInput(
            nombre=body.nombre,
            categoria_padre_id=body.categoria_padre_id
        ))
        return categoria
    except CategoriaNoEncontrada as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/productos", response_model=ProductoResponse, status_code=status.HTTP_201_CREATED)
async def crear_producto(
    body: CrearProductoRequest,
    use_case: CrearProductoUseCase = Depends(get_crear_producto_use_case),
):
    try:
        producto = await use_case.ejecutar(CrearProductoInput(
            sku=body.sku,
            nombre=body.nombre,
            categoria_id=body.categoria_id,
            unidad_medida=body.unidad_medida,
            precio_venta=body.precio_venta,
            costo=body.costo,
            impuesto_tasa=body.impuesto_tasa,
            permite_stock_negativo=body.permite_stock_negativo,
            codigo_barras=body.codigo_barras,
            descripcion=body.descripcion
        ))
        return producto
    except CategoriaNoEncontrada as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/movimientos", status_code=status.HTTP_201_CREATED)
async def aplicar_movimiento(
    body: AplicarMovimientoRequest,
    use_case: AplicarMovimientoUseCase = Depends(get_aplicar_movimiento_use_case),
    usuario_actual: Usuario = Depends(get_current_user)
):
    if not usuario_actual.sucursal_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El usuario no tiene una sucursal asignada")

    try:
        await use_case.ejecutar(AplicarMovimientoInput(
            producto_id=body.producto_id,
            sucursal_id=usuario_actual.sucursal_id,
            tipo=body.tipo,
            cantidad=body.cantidad,
            referencia_tipo=body.referencia_tipo,
            usuario_id=usuario_actual.id,
            referencia_id=body.referencia_id,
            costo_unitario=body.costo_unitario,
            motivo=body.motivo
        ))
        return {"status": "ok"}
    except (ProductoNoEncontrado, StockInsuficiente, ValueError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
