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
    PromocionNoEncontrada, PromocionInvalida, CuponNoEncontrado,
)
from app.modules.promociones.infrastructure.persistence.promocion_repository_impl import (
    SqlAlchemyPromocionRepository,
)
from app.modules.promociones.infrastructure.persistence.cupon_repository_impl import (
    SqlAlchemyCuponRepository,
)
from app.modules.promociones.application.use_cases.gestionar_cupones import (
    CrearCuponUseCase, CrearCuponInput, ListarCuponesUseCase, DesactivarCuponUseCase,
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
    if isinstance(e, (PromocionNoEncontrada, CuponNoEncontrado)):
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
        ObjetivoInput(
            producto_id=o.producto_id, producto_unidad_id=o.producto_unidad_id,
            categoria_id=o.categoria_id,
        )
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
            prioridad=body.prioridad, activo=body.activo, sucursales=body.sucursales,
            vigente_desde=body.vigente_desde, vigente_hasta=body.vigente_hasta,
            hora_desde=body.hora_desde, hora_hasta=body.hora_hasta,
            dias_semana=body.dias_semana,
            nxm_lleva=body.nxm_lleva, nxm_paga=body.nxm_paga,
            descuento_pct=body.descuento_pct, precio_fijo=body.precio_fijo,
            cantidad_minima=body.cantidad_minima,
            combinable=body.combinable, tope_descuento=body.tope_descuento,
            monto_minimo_compra=body.monto_minimo_compra,
            metodo_pago_requerido=body.metodo_pago_requerido,
            cliente_segmento=body.cliente_segmento,
            requiere_cupon=body.requiere_cupon,
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
            sucursales=body.sucursales, cambiar_sucursales=body.cambiar_sucursales,
            vigente_desde=body.vigente_desde, vigente_hasta=body.vigente_hasta,
            cambiar_vigencia=body.cambiar_vigencia,
            hora_desde=body.hora_desde, hora_hasta=body.hora_hasta,
            dias_semana=body.dias_semana, cambiar_horario=body.cambiar_horario,
            nxm_lleva=body.nxm_lleva, nxm_paga=body.nxm_paga,
            descuento_pct=body.descuento_pct, precio_fijo=body.precio_fijo,
            cantidad_minima=body.cantidad_minima,
            cambiar_cantidad_minima=body.cambiar_cantidad_minima,
            combinable=body.combinable, tope_descuento=body.tope_descuento,
            monto_minimo_compra=body.monto_minimo_compra, cambiar_topes=body.cambiar_topes,
            metodo_pago_requerido=body.metodo_pago_requerido,
            cliente_segmento=body.cliente_segmento, requiere_cupon=body.requiere_cupon,
            cambiar_condiciones=body.cambiar_condiciones,
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


# --------------------------------------------------------------------------- #
# Cupones
# --------------------------------------------------------------------------- #
from datetime import datetime  # noqa: E402
from decimal import Decimal  # noqa: E402
from typing import Optional  # noqa: E402
from pydantic import BaseModel, ConfigDict, Field  # noqa: E402


class _CrearCuponRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    codigo: str = Field(min_length=1, max_length=40)
    vigente_desde: Optional[datetime] = None
    vigente_hasta: Optional[datetime] = None
    max_usos_total: Optional[int] = Field(default=None, ge=1)
    max_usos_por_persona: Optional[int] = Field(default=None, ge=1)


class _CuponResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    codigo: str
    promocion_id: UUID
    activo: bool
    vigente_desde: Optional[datetime] = None
    vigente_hasta: Optional[datetime] = None
    max_usos_total: Optional[int] = None
    max_usos_por_persona: Optional[int] = None
    created_at: datetime


def _cupon_repo(db: AsyncSession) -> SqlAlchemyCuponRepository:
    return SqlAlchemyCuponRepository(db)


@router.post(
    "/{promocion_id}/cupones", response_model=ApiResponse[_CuponResponse],
    status_code=status.HTTP_201_CREATED,
)
async def crear_cupon(
    promocion_id: UUID,
    body: _CrearCuponRequest,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("promociones.crear")),
):
    try:
        cupon = await CrearCuponUseCase(_cupon_repo(db), _repo(db)).ejecutar(CrearCuponInput(
            promocion_id=promocion_id, codigo=body.codigo,
            vigente_desde=body.vigente_desde, vigente_hasta=body.vigente_hasta,
            max_usos_total=body.max_usos_total,
            max_usos_por_persona=body.max_usos_por_persona,
        ))
    except Exception as e:
        raise _traducir(e)
    return ok(cupon)


@router.get("/{promocion_id}/cupones", response_model=ApiResponse[list[_CuponResponse]])
async def listar_cupones(
    promocion_id: UUID,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("promociones.leer")),
):
    cupones = await ListarCuponesUseCase(_cupon_repo(db)).ejecutar(promocion_id)
    return ok(cupones)


@router.patch("/cupones/{codigo}/desactivar", response_model=ApiResponse[_CuponResponse])
async def desactivar_cupon(
    codigo: str,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("promociones.editar")),
):
    try:
        cupon = await DesactivarCuponUseCase(_cupon_repo(db)).ejecutar(codigo)
    except Exception as e:
        raise _traducir(e)
    return ok(cupon)
