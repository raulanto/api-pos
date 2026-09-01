from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_permission, UsuarioAutenticado
from app.shared.responses import (
    ApiResponse, EnvelopeRoute, PageParams, Sort,
    page_params, make_sort_dependency, make_include_dependency, ok, page_response,
)
from app.shared.filtering import active_filters
from app.modules.inventario.application.dtos import FiltroCategorias
from app.modules.inventario.application.use_cases.crear_categoria import (
    CrearCategoriaUseCase, CrearCategoriaInput,
)
from app.modules.inventario.application.use_cases.gestionar_categorias import (
    ListarCategoriasUseCase, ObtenerCategoriaUseCase,
    ActualizarCategoriaUseCase, ActualizarCategoriaInput, DesactivarCategoriaUseCase,
)
from app.modules.inventario.infrastructure.api.schemas import (
    CrearCategoriaRequest, ActualizarCategoriaRequest, CategoriaResponse,
)
from .common import cat_repo, traducir, traducir_create

router = APIRouter(route_class=EnvelopeRoute)

_ORDEN_CAT = make_sort_dependency({"nombre"}, "nombre:asc")
_INC_CAT = make_include_dependency({"padre"})


@router.post(
    "/categorias", response_model=ApiResponse[CategoriaResponse],
    status_code=status.HTTP_201_CREATED,
)
async def crear_categoria(
    body: CrearCategoriaRequest,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("inventario.crear")),
):
    try:
        categoria = await CrearCategoriaUseCase(cat_repo(db)).ejecutar(
            CrearCategoriaInput(nombre=body.nombre, categoria_padre_id=body.categoria_padre_id)
        )
    except Exception as e:
        raise traducir_create(e)
    return ok(categoria)


@router.get("/categorias", response_model=ApiResponse[list[CategoriaResponse]])
async def listar_categorias(
    request: Request,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("inventario.leer")),
    activo: bool | None = Query(default=None),
    categoria_padre_id: UUID | None = Query(default=None),
    q: str | None = Query(default=None, description="Busca en el nombre"),
    paginacion: PageParams = Depends(page_params),
    orden: Sort = Depends(_ORDEN_CAT),
    include: frozenset[str] = Depends(_INC_CAT),
):
    filtro = FiltroCategorias(
        activo=activo, categoria_padre_id=categoria_padre_id, busqueda=q,
    )
    pagina = await ListarCategoriasUseCase(cat_repo(db)).ejecutar(
        filtro, paginacion, orden, include,
    )
    return page_response(
        request, pagina, paginacion, sort=orden, filters=active_filters(filtro),
    )


@router.get("/categorias/{categoria_id}", response_model=ApiResponse[CategoriaResponse])
async def obtener_categoria(
    categoria_id: UUID,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("inventario.leer")),
    include: frozenset[str] = Depends(_INC_CAT),
):
    try:
        categoria = await ObtenerCategoriaUseCase(cat_repo(db)).ejecutar(categoria_id, include)
    except Exception as e:
        raise traducir(e)
    return ok(categoria)


@router.patch("/categorias/{categoria_id}", response_model=ApiResponse[CategoriaResponse])
async def actualizar_categoria(
    categoria_id: UUID,
    body: ActualizarCategoriaRequest,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("inventario.editar")),
):
    try:
        categoria = await ActualizarCategoriaUseCase(cat_repo(db)).ejecutar(
            ActualizarCategoriaInput(
                categoria_id=categoria_id,
                nombre=body.nombre,
                categoria_padre_id=body.categoria_padre_id,
                cambiar_padre=body.cambiar_padre,
            )
        )
    except Exception as e:
        raise traducir(e)
    return ok(categoria)


@router.patch(
    "/categorias/{categoria_id}/desactivar", response_model=ApiResponse[CategoriaResponse],
)
async def desactivar_categoria(
    categoria_id: UUID,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("inventario.editar")),
):
    try:
        categoria = await DesactivarCategoriaUseCase(cat_repo(db)).ejecutar(categoria_id)
    except Exception as e:
        raise traducir(e)
    return ok(categoria)
