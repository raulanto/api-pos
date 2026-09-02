from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_permission, UsuarioAutenticado
from app.shared.responses import (
    ApiResponse, EnvelopeRoute, PageParams, Sort,
    page_params, make_sort_dependency, ok, page_response,
)
from app.shared.filtering import active_filters
from app.modules.usuarios.application.dto import FiltroSucursales
from app.modules.usuarios.infrastructure.api.schemas import (
    CrearSucursalRequest, ActualizarSucursalRequest, SucursalResponse,
)
from app.modules.usuarios.infrastructure.persistence.catalogos_repository_impl import (
    SqlAlchemySucursalRepository,
)
from app.modules.usuarios.application.use_cases.gestionar_sucursales import (
    ListarSucursalesUseCase, ObtenerSucursalUseCase,
    CrearSucursalUseCase, CrearSucursalInput,
    ActualizarSucursalUseCase, ActualizarSucursalInput,
    DesactivarSucursalUseCase, ReactivarSucursalUseCase,
)
from app.modules.usuarios.domain.exceptions import (
    SucursalNoEncontrada, NombreSucursalDuplicado, SucursalConUsuariosActivos,
)

router = APIRouter(route_class=EnvelopeRoute)

_ORDEN_SUCURSALES = make_sort_dependency({"nombre", "created_at"}, "nombre:asc")
_CONFLICT = (NombreSucursalDuplicado, SucursalConUsuariosActivos)


def _sucursal_repo(db: AsyncSession) -> SqlAlchemySucursalRepository:
    return SqlAlchemySucursalRepository(db)


@router.get("", response_model=ApiResponse[list[SucursalResponse]])
async def listar_sucursales(
    request: Request,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("sucursales.leer")),
    activo: bool | None = Query(default=None),
    q: str | None = Query(default=None, description="Busca en nombre, dirección y teléfono"),
    paginacion: PageParams = Depends(page_params),
    orden: Sort = Depends(_ORDEN_SUCURSALES),
):
    filtro = FiltroSucursales(activo=activo, busqueda=q)
    pagina = await ListarSucursalesUseCase(_sucursal_repo(db)).ejecutar(
        filtro, paginacion, orden,
    )
    return page_response(
        request, pagina, paginacion, sort=orden, filters=active_filters(filtro),
    )


@router.post(
    "", response_model=ApiResponse[SucursalResponse], status_code=status.HTTP_201_CREATED,
)
async def crear_sucursal(
    body: CrearSucursalRequest,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("sucursales.crear")),
):
    try:
        sucursal = await CrearSucursalUseCase(_sucursal_repo(db)).ejecutar(
            CrearSucursalInput(
                nombre=body.nombre, direccion=body.direccion, telefono=body.telefono,
            )
        )
    except _CONFLICT as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    return ok(sucursal)


@router.get("/{sucursal_id}", response_model=ApiResponse[SucursalResponse])
async def obtener_sucursal(
    sucursal_id: UUID,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("sucursales.leer")),
):
    try:
        sucursal = await ObtenerSucursalUseCase(_sucursal_repo(db)).ejecutar(sucursal_id)
    except SucursalNoEncontrada as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return ok(sucursal)


@router.patch("/{sucursal_id}", response_model=ApiResponse[SucursalResponse])
async def actualizar_sucursal(
    sucursal_id: UUID,
    body: ActualizarSucursalRequest,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("sucursales.editar")),
):
    try:
        sucursal = await ActualizarSucursalUseCase(_sucursal_repo(db)).ejecutar(
            ActualizarSucursalInput(
                sucursal_id=sucursal_id,
                nombre=body.nombre,
                direccion=body.direccion,
                telefono=body.telefono,
            )
        )
    except SucursalNoEncontrada as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except _CONFLICT as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    return ok(sucursal)


@router.patch(
    "/{sucursal_id}/desactivar", response_model=ApiResponse[SucursalResponse],
)
async def desactivar_sucursal(
    sucursal_id: UUID,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("sucursales.desactivar")),
):
    try:
        sucursal = await DesactivarSucursalUseCase(_sucursal_repo(db)).ejecutar(sucursal_id)
    except SucursalNoEncontrada as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except _CONFLICT as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    return ok(sucursal)


@router.patch(
    "/{sucursal_id}/reactivar", response_model=ApiResponse[SucursalResponse],
)
async def reactivar_sucursal(
    sucursal_id: UUID,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("sucursales.desactivar")),
):
    try:
        sucursal = await ReactivarSucursalUseCase(_sucursal_repo(db)).ejecutar(sucursal_id)
    except SucursalNoEncontrada as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return ok(sucursal)
