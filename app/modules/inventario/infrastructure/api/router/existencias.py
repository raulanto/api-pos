from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_permission, UsuarioAutenticado, verificar_alcance_sucursal
from app.modules.inventario.application.use_cases.consultar_existencias import (
    ConsultarExistenciasUseCase, ListarBajoStockUseCase,
    ConfigurarUmbralesUseCase, ConfigurarUmbralesInput,
)
from app.modules.inventario.infrastructure.api.schemas import (
    ExistenciaResponse, ConfigurarUmbralesRequest,
)
from .common import exist_repo, prod_repo, sucursal_efectiva, traducir

router = APIRouter()

"""
    Endpoint para listar existencias.

    @param db: Sesión de la base de datos.
    @param actual: Usuario autenticado.
    @param producto_id: ID del producto.
    @param sucursal_id: ID de la sucursal.
    @return: Instancia de la clase ExistenciaResponse.
"""
@router.get("/existencias", response_model=list[ExistenciaResponse])
async def listar_existencias(
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("inventario.leer")),
    producto_id: UUID | None = Query(default=None),
    sucursal_id: UUID | None = Query(default=None),
):
    efectivo = sucursal_efectiva(actual, sucursal_id)
    return await ConsultarExistenciasUseCase(exist_repo(db)).ejecutar(
        producto_id=producto_id, sucursal_id=efectivo
    )

"""
    Endpoint para listar existencias bajo stock.

    @param db: Sesión de la base de datos.
    @param actual: Usuario autenticado.
    @param sucursal_id: ID de la sucursal.
    @return: Instancia de la clase ExistenciaResponse.
"""
@router.get("/existencias/bajo-stock", response_model=list[ExistenciaResponse])
async def listar_bajo_stock(
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("inventario.leer")),
    sucursal_id: UUID | None = Query(default=None),
):
    efectivo = sucursal_efectiva(actual, sucursal_id)
    return await ListarBajoStockUseCase(exist_repo(db)).ejecutar(sucursal_id=efectivo)

"""
    Endpoint para configurar umbrales de stock.

    @param producto_id: ID del producto.
    @param sucursal_id: ID de la sucursal.
    @param body: Cuerpo de la solicitud.
    @param db: Sesión de la base de datos.
    @param actual: Usuario autenticado.
    @return: Instancia de la clase ExistenciaResponse.
"""
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
        existencia = await ConfigurarUmbralesUseCase(exist_repo(db), prod_repo(db)).ejecutar(
            ConfigurarUmbralesInput(
                producto_id=producto_id, sucursal_id=sucursal_id,
                stock_minimo=body.stock_minimo, stock_maximo=body.stock_maximo,
            )
        )
    except Exception as e:
        raise traducir(e)
    return existencia
