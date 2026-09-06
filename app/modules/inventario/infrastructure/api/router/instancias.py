from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_permission, UsuarioAutenticado
from app.shared.responses import (
    ApiResponse, EnvelopeRoute, PageParams, Sort,
    page_params, make_sort_dependency, ok, page_response,
)
from app.modules.inventario.application.dtos import FiltroInstancias
from app.modules.inventario.domain.value_objects import EstadoInstancia
from app.modules.inventario.application.use_cases.aplicar_movimiento import (
    AplicarMovimientoUseCase,
)
from app.modules.inventario.application.use_cases.gestionar_instancias import (
    AbrirInstanciaUseCase, AbrirInstanciaInput,
    ListarInstanciasUseCase, ObtenerInstanciaUseCase,
    ConsumirInstanciaUseCase, ConsumirInstanciaInput,
    MermarInstanciaUseCase, MermarInstanciaInput,
    AjustarInstanciaUseCase, AjustarInstanciaInput,
    DescartarInstanciaUseCase, DescartarInstanciaInput,
)
from app.modules.inventario.infrastructure.adapters.event_port_impl import EventPortImpl
from app.modules.inventario.infrastructure.api.schemas import (
    AbrirInstanciaRequest, ConsumirInstanciaRequest, MermarInstanciaRequest,
    AjustarInstanciaRequest, DescartarInstanciaRequest, InstanciaResponse,
)
from .common import (
    inst_repo, prod_repo, exist_repo, mov_repo, um_repo, lote_repo, unidad_repo,
    sucursal_efectiva, sucursales_efectivas, traducir,
)

router = APIRouter(route_class=EnvelopeRoute)

_ORDEN_INST = make_sort_dependency({"abierta_at", "saldo", "created_at"}, "abierta_at:desc")


def _motor_movimiento(db: AsyncSession) -> AplicarMovimientoUseCase:
    return AplicarMovimientoUseCase(
        prod_repo(db), exist_repo(db), mov_repo(db), EventPortImpl(db),
        um_repo(db), lote_repo(db),
    )


# --------------------------------------------------------------------------- #
# Galería de instancias abiertas de un producto
# --------------------------------------------------------------------------- #
@router.get(
    "/productos/{producto_id}/instancias",
    response_model=ApiResponse[list[InstanciaResponse]],
)
async def listar_instancias_producto(
    producto_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("inventario.leer")),
    paginacion: PageParams = Depends(page_params),
    orden: Sort = Depends(_ORDEN_INST),
    sucursal_id: list[UUID] | None = Query(default=None),
    estado: EstadoInstancia | None = Query(default=None),
):
    filtro = FiltroInstancias(
        producto_id=producto_id,
        sucursal_id=sucursales_efectivas(actual, sucursal_id),
        estado=estado,
    )
    pagina = await ListarInstanciasUseCase(inst_repo(db)).ejecutar(
        filtro, paginacion, orden,
    )
    return page_response(request, pagina, paginacion, sort=orden)


@router.post(
    "/productos/{producto_id}/instancias/abrir",
    response_model=ApiResponse[InstanciaResponse], status_code=status.HTTP_201_CREATED,
)
async def abrir_instancia(
    producto_id: UUID,
    body: AbrirInstanciaRequest,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("inventario.movimiento")),
):
    sucursal = sucursal_efectiva(actual, body.sucursal_id)
    if sucursal is None:
        raise traducir(ValueError("Indicá `sucursal_id` para abrir el envase."))
    try:
        instancia = await AbrirInstanciaUseCase(
            prod_repo(db), exist_repo(db), inst_repo(db), unidad_repo(db),
            lote_repo(db), EventPortImpl(db),
        ).ejecutar(AbrirInstanciaInput(
            producto_id=producto_id,
            sucursal_id=sucursal,
            usuario_id=actual.id,
            producto_unidad_id=body.producto_unidad_id,
            capacidad=body.capacidad,
            lote_id=body.lote_id,
            motivo=body.motivo,
        ))
    except Exception as e:
        raise traducir(e)
    return ok(instancia)


# --------------------------------------------------------------------------- #
# Operaciones sobre una instancia
# --------------------------------------------------------------------------- #
@router.get("/instancias/{instancia_id}", response_model=ApiResponse[InstanciaResponse])
async def obtener_instancia(
    instancia_id: UUID,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("inventario.leer")),
):
    try:
        instancia = await ObtenerInstanciaUseCase(inst_repo(db)).ejecutar(instancia_id)
    except Exception as e:
        raise traducir(e)
    return ok(instancia)


@router.post(
    "/instancias/{instancia_id}/consumir", response_model=ApiResponse[InstanciaResponse],
)
async def consumir_instancia(
    instancia_id: UUID,
    body: ConsumirInstanciaRequest,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("inventario.movimiento")),
):
    try:
        instancia = await ConsumirInstanciaUseCase(
            inst_repo(db), _motor_movimiento(db),
        ).ejecutar(ConsumirInstanciaInput(
            instancia_id=instancia_id, cantidad=body.cantidad,
            usuario_id=actual.id, motivo=body.motivo,
        ))
    except Exception as e:
        raise traducir(e)
    return ok(instancia)


@router.post(
    "/instancias/{instancia_id}/merma", response_model=ApiResponse[InstanciaResponse],
)
async def mermar_instancia(
    instancia_id: UUID,
    body: MermarInstanciaRequest,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("inventario.movimiento")),
):
    try:
        instancia = await MermarInstanciaUseCase(
            inst_repo(db), _motor_movimiento(db),
        ).ejecutar(MermarInstanciaInput(
            instancia_id=instancia_id, cantidad=body.cantidad,
            usuario_id=actual.id, motivo=body.motivo,
        ))
    except Exception as e:
        raise traducir(e)
    return ok(instancia)


@router.post(
    "/instancias/{instancia_id}/ajustar", response_model=ApiResponse[InstanciaResponse],
)
async def ajustar_instancia(
    instancia_id: UUID,
    body: AjustarInstanciaRequest,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("inventario.movimiento")),
):
    try:
        instancia = await AjustarInstanciaUseCase(
            inst_repo(db), _motor_movimiento(db),
        ).ejecutar(AjustarInstanciaInput(
            instancia_id=instancia_id, saldo_medido=body.saldo_medido,
            usuario_id=actual.id, motivo=body.motivo,
        ))
    except Exception as e:
        raise traducir(e)
    return ok(instancia)


@router.post(
    "/instancias/{instancia_id}/descartar", response_model=ApiResponse[InstanciaResponse],
)
async def descartar_instancia(
    instancia_id: UUID,
    body: DescartarInstanciaRequest,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("inventario.movimiento")),
):
    try:
        instancia = await DescartarInstanciaUseCase(
            inst_repo(db), _motor_movimiento(db),
        ).ejecutar(DescartarInstanciaInput(
            instancia_id=instancia_id, usuario_id=actual.id, motivo=body.motivo,
        ))
    except Exception as e:
        raise traducir(e)
    return ok(instancia)
