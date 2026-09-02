from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_permission, UsuarioAutenticado, verificar_alcance_sucursal
from app.shared.responses import (
    ApiResponse, EnvelopeRoute, PageParams, Sort,
    page_params, make_sort_dependency, make_include_dependency, ok, page_response,
)
from app.shared.filtering import active_filters
from app.modules.inventario.application.dtos import FiltroExistencias
from app.modules.inventario.application.use_cases.consultar_existencias import (
    ConsultarExistenciasUseCase, ConfigurarUmbralesUseCase, ConfigurarUmbralesInput,
)
from app.modules.inventario.infrastructure.api.schemas import (
    ExistenciaResponse, ConfigurarUmbralesRequest,
)
from .common import exist_repo, prod_repo, sucursales_efectivas, traducir

router = APIRouter(route_class=EnvelopeRoute)

_ORDEN_EXIST = make_sort_dependency(
    {"cantidad", "stock_minimo", "updated_at"}, "updated_at:desc"
)
_INC_EXIST = make_include_dependency({"producto"})


async def _listar(request, db, actual, producto_id, sucursal_id, paginacion, orden, include, solo_bajo_stock):
    efectivas = sucursales_efectivas(actual, sucursal_id)
    filtro = FiltroExistencias(
        producto_id=producto_id, sucursal_id=efectivas, solo_bajo_stock=solo_bajo_stock,
    )
    pagina = await ConsultarExistenciasUseCase(exist_repo(db)).ejecutar(
        filtro, paginacion, orden, include,
    )
    return page_response(
        request, pagina, paginacion, sort=orden, filters=active_filters(filtro),
    )


@router.get("/existencias", response_model=ApiResponse[list[ExistenciaResponse]])
async def listar_existencias(
    request: Request,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("inventario.leer")),
    producto_id: UUID | None = Query(default=None),
    sucursal_id: list[UUID] | None = Query(default=None),
    paginacion: PageParams = Depends(page_params),
    orden: Sort = Depends(_ORDEN_EXIST),
    include: frozenset[str] = Depends(_INC_EXIST),
):
    return await _listar(
        request, db, actual, producto_id, sucursal_id, paginacion, orden, include,
        solo_bajo_stock=False,
    )


@router.get("/existencias/bajo-stock", response_model=ApiResponse[list[ExistenciaResponse]])
async def listar_bajo_stock(
    request: Request,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("inventario.leer")),
    sucursal_id: list[UUID] | None = Query(default=None),
    paginacion: PageParams = Depends(page_params),
    orden: Sort = Depends(_ORDEN_EXIST),
    include: frozenset[str] = Depends(_INC_EXIST),
):
    return await _listar(
        request, db, actual, None, sucursal_id, paginacion, orden, include,
        solo_bajo_stock=True,
    )


@router.patch(
    "/existencias/{producto_id}/{sucursal_id}/umbrales",
    response_model=ApiResponse[ExistenciaResponse],
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
    return ok(existencia)
