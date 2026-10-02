from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_permission, UsuarioAutenticado
from app.shared.responses import (
    ApiResponse, EnvelopeRoute, PageParams, Sort,
    page_params, make_sort_dependency, ok, page_response,
)
from app.shared.filtering import active_filters
from app.shared.events import event_bus
from app.shared.client_info import obtener_ip_cliente
from app.modules.inventario.application.dtos import FiltroMarcas
from app.modules.inventario.application.use_cases.gestionar_marcas import (
    CrearMarcaUseCase, CrearMarcaInput, ListarMarcasUseCase, ObtenerMarcaUseCase,
    ActualizarMarcaUseCase, ActualizarMarcaInput, DesactivarMarcaUseCase, ReactivarMarcaUseCase,
    EliminarMarcaUseCase,
)
from app.modules.inventario.infrastructure.api.schemas import (
    CrearMarcaRequest, ActualizarMarcaRequest, MarcaResponse,
)
from .common import marca_repo, traducir, traducir_create

router = APIRouter(route_class=EnvelopeRoute)

_ORDEN_MARCA = make_sort_dependency({"nombre"}, "nombre:asc")


@router.post(
    "/marcas", response_model=ApiResponse[MarcaResponse],
    status_code=status.HTTP_201_CREATED,
)
async def crear_marca(
    body: CrearMarcaRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("inventario.crear")),
):
    try:
        marca = await CrearMarcaUseCase(marca_repo(db)).ejecutar(
            CrearMarcaInput(nombre=body.nombre)
        )
        await event_bus.publicar("MarcaCreada", {
            "usuario_id": actual.id,
            "modulo": "inventario",
            "accion": "crear_marca",
            "entidad": "Marca",
            "entidad_id": str(marca.id),
            "detalle": {"nombre": marca.nombre},
            "ip_address": obtener_ip_cliente(request),
        }, db)
    except Exception as e:
        raise traducir_create(e)
    return ok(marca)


@router.get("/marcas", response_model=ApiResponse[list[MarcaResponse]])
async def listar_marcas(
    request: Request,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("inventario.leer")),
    activo: bool | None = Query(default=None),
    q: str | None = Query(default=None, description="Busca en el nombre"),
    paginacion: PageParams = Depends(page_params),
    orden: Sort = Depends(_ORDEN_MARCA),
):
    filtro = FiltroMarcas(
        activo=activo, busqueda=q,
    )
    pagina = await ListarMarcasUseCase(marca_repo(db)).ejecutar(
        filtro, paginacion, orden,
    )
    return page_response(
        request, pagina, paginacion, sort=orden, filters=active_filters(filtro),
    )


@router.get("/marcas/{marca_id}", response_model=ApiResponse[MarcaResponse])
async def obtener_marca(
    marca_id: UUID,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("inventario.leer")),
):
    try:
        marca = await ObtenerMarcaUseCase(marca_repo(db)).ejecutar(marca_id)
    except Exception as e:
        raise traducir(e)
    return ok(marca)


@router.patch("/marcas/{marca_id}", response_model=ApiResponse[MarcaResponse])
async def actualizar_marca(
    marca_id: UUID,
    body: ActualizarMarcaRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("inventario.editar")),
):
    try:
        marca = await ActualizarMarcaUseCase(marca_repo(db)).ejecutar(
            ActualizarMarcaInput(
                marca_id=marca_id,
                nombre=body.nombre,
            )
        )
        await event_bus.publicar("MarcaEditada", {
            "usuario_id": actual.id,
            "modulo": "inventario",
            "accion": "editar_marca",
            "entidad": "Marca",
            "entidad_id": str(marca.id),
            "detalle": {"nombre": marca.nombre},
            "ip_address": obtener_ip_cliente(request),
        }, db)
    except Exception as e:
        raise traducir(e)
    return ok(marca)


@router.patch(
    "/marcas/{marca_id}/desactivar", response_model=ApiResponse[MarcaResponse],
)
async def desactivar_marca(
    marca_id: UUID,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("inventario.editar")),
):
    try:
        marca = await DesactivarMarcaUseCase(marca_repo(db)).ejecutar(marca_id)
    except Exception as e:
        raise traducir(e)
    return ok(marca)


@router.patch(
    "/marcas/{marca_id}/activar", response_model=ApiResponse[MarcaResponse],
)
async def activar_marca(
    marca_id: UUID,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("inventario.editar")),
):
    try:
        marca = await ReactivarMarcaUseCase(marca_repo(db)).ejecutar(marca_id)
    except Exception as e:
        raise traducir(e)
    return ok(marca)


@router.delete(
    "/marcas/{marca_id}", status_code=status.HTTP_204_NO_CONTENT,
)
async def eliminar_marca(
    marca_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("inventario.eliminar")),
):
    try:
        await EliminarMarcaUseCase(marca_repo(db)).ejecutar(marca_id)
        await event_bus.publicar("MarcaEliminada", {
            "usuario_id": actual.id,
            "modulo": "inventario",
            "accion": "eliminar_marca",
            "entidad": "Marca",
            "entidad_id": str(marca_id),
            "ip_address": obtener_ip_cliente(request),
        }, db)
    except Exception as e:
        raise traducir(e)

