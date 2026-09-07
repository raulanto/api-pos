from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_permission, UsuarioAutenticado
from app.shared.responses import (
    ApiResponse, EnvelopeRoute, PageParams, Sort,
    page_params, make_sort_dependency, ok, page_response,
)
from app.shared.filtering import active_filters
from app.modules.promociones.application.dtos import FiltroPromociones
from app.modules.promociones.domain.entities import TipoPromocion
from app.modules.promociones.domain.exceptions import (
    PromocionNoEncontrada, PromocionInvalida,
)
from app.modules.promociones.infrastructure.persistence.promocion_repository_impl import (
    SqlAlchemyPromocionRepository,
)
from app.modules.promociones.infrastructure.api.schemas import (
    CrearPromocionRequest, ActualizarPromocionRequest, PromocionResponse,
)
from app.modules.promociones.application.use_cases.gestionar_promociones import (
    ListarPromocionesUseCase, ObtenerPromocionUseCase,
    CrearPromocionUseCase, CrearPromocionInput,
    ActualizarPromocionUseCase, ActualizarPromocionInput,
    DesactivarPromocionUseCase, ReactivarPromocionUseCase,
    ObjetivoInput,
)

router = APIRouter(route_class=EnvelopeRoute)

_ORDEN = make_sort_dependency({"nombre", "prioridad", "created_at"}, "prioridad:asc")


def _repo(db: AsyncSession) -> SqlAlchemyPromocionRepository:
    return SqlAlchemyPromocionRepository(db)


def _traducir(e: Exception) -> HTTPException:
    if isinstance(e, PromocionNoEncontrada):
        return HTTPException(status.HTTP_404_NOT_FOUND, detail=str(e))
    if isinstance(e, IntegrityError):
        return HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Conflicto de datos: nombre repetido o producto/presentación inexistente.",
        )
    if isinstance(e, (PromocionInvalida, ValueError)):
        return HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e))
    raise e


def _objetivos(body_objetivos) -> list[ObjetivoInput]:
    return [
        ObjetivoInput(producto_id=o.producto_id, producto_unidad_id=o.producto_unidad_id)
        for o in body_objetivos
    ]


@router.get("", response_model=ApiResponse[list[PromocionResponse]])
async def listar_promociones(
    request: Request,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("promociones.leer")),
    activo: bool | None = Query(default=None),
    tipo: TipoPromocion | None = Query(default=None),
    sucursal_id: UUID | None = Query(default=None),
    q: str | None = Query(default=None, description="Busca en el nombre"),
    paginacion: PageParams = Depends(page_params),
    orden: Sort = Depends(_ORDEN),
):
    filtro = FiltroPromociones(activo=activo, tipo=tipo, sucursal_id=sucursal_id, busqueda=q)
    pagina = await ListarPromocionesUseCase(_repo(db)).ejecutar(filtro, paginacion, orden)
    return page_response(
        request, pagina, paginacion, sort=orden, filters=active_filters(filtro),
    )


@router.post(
    "", response_model=ApiResponse[PromocionResponse], status_code=status.HTTP_201_CREATED,
)
async def crear_promocion(
    body: CrearPromocionRequest,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("promociones.crear")),
):
    try:
        promo = await CrearPromocionUseCase(_repo(db)).ejecutar(CrearPromocionInput(
            nombre=body.nombre, tipo=body.tipo, objetivos=_objetivos(body.objetivos),
            prioridad=body.prioridad, activo=body.activo, sucursal_id=body.sucursal_id,
            vigente_desde=body.vigente_desde, vigente_hasta=body.vigente_hasta,
            nxm_lleva=body.nxm_lleva, nxm_paga=body.nxm_paga,
            descuento_pct=body.descuento_pct, precio_fijo=body.precio_fijo,
            cantidad_minima=body.cantidad_minima,
        ))
    except Exception as e:
        raise _traducir(e)
    return ok(promo)


@router.get("/{promocion_id}", response_model=ApiResponse[PromocionResponse])
async def obtener_promocion(
    promocion_id: UUID,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("promociones.leer")),
):
    try:
        promo = await ObtenerPromocionUseCase(_repo(db)).ejecutar(promocion_id)
    except Exception as e:
        raise _traducir(e)
    return ok(promo)


@router.patch("/{promocion_id}", response_model=ApiResponse[PromocionResponse])
async def actualizar_promocion(
    promocion_id: UUID,
    body: ActualizarPromocionRequest,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("promociones.editar")),
):
    try:
        promo = await ActualizarPromocionUseCase(_repo(db)).ejecutar(ActualizarPromocionInput(
            promocion_id=promocion_id,
            nombre=body.nombre, prioridad=body.prioridad, activo=body.activo,
            tipo=body.tipo,
            sucursal_id=body.sucursal_id, cambiar_sucursal=body.cambiar_sucursal,
            vigente_desde=body.vigente_desde, vigente_hasta=body.vigente_hasta,
            cambiar_vigencia=body.cambiar_vigencia,
            nxm_lleva=body.nxm_lleva, nxm_paga=body.nxm_paga,
            descuento_pct=body.descuento_pct, precio_fijo=body.precio_fijo,
            cantidad_minima=body.cantidad_minima,
            cambiar_cantidad_minima=body.cambiar_cantidad_minima,
            objetivos=_objetivos(body.objetivos) if body.objetivos is not None else None,
        ))
    except Exception as e:
        raise _traducir(e)
    return ok(promo)


@router.patch("/{promocion_id}/desactivar", response_model=ApiResponse[PromocionResponse])
async def desactivar_promocion(
    promocion_id: UUID,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("promociones.editar")),
):
    try:
        promo = await DesactivarPromocionUseCase(_repo(db)).ejecutar(promocion_id)
    except Exception as e:
        raise _traducir(e)
    return ok(promo)


@router.patch("/{promocion_id}/reactivar", response_model=ApiResponse[PromocionResponse])
async def reactivar_promocion(
    promocion_id: UUID,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("promociones.editar")),
):
    try:
        promo = await ReactivarPromocionUseCase(_repo(db)).ejecutar(promocion_id)
    except Exception as e:
        raise _traducir(e)
    return ok(promo)
