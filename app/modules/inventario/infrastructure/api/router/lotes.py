from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_permission, UsuarioAutenticado
from app.shared.responses import ApiResponse, EnvelopeRoute, ok
from app.modules.inventario.application.use_cases.gestionar_lotes import (
    ListarLotesUseCase, ObtenerLoteUseCase,
    CrearLoteUseCase, CrearLoteInput,
    ActualizarLoteUseCase, ActualizarLoteInput,
    DesactivarLoteUseCase, LotesPorVencerUseCase,
)
from app.modules.inventario.infrastructure.api.schemas import (
    CrearLoteRequest, ActualizarLoteRequest, LoteResponse, LotePorVencerResponse,
)
from .common import lote_repo, prod_repo, sucursales_efectivas, traducir

router = APIRouter(route_class=EnvelopeRoute)


@router.get(
    "/lotes/por-vencer", response_model=ApiResponse[list[LotePorVencerResponse]],
)
async def lotes_por_vencer(
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("inventario.leer")),
    dias: int = Query(default=30, ge=0, le=3650),
    sucursal_id: list[UUID] | None = Query(default=None),
):
    """Lotes que caducan dentro de `dias` (incluye vencidos), con su saldo por
    sucursal. Para el panel de control de caducidades."""
    efectivas = sucursales_efectivas(actual, sucursal_id)
    filas = await LotesPorVencerUseCase(lote_repo(db)).ejecutar(dias, efectivas)
    return ok([
        LotePorVencerResponse(
            lote=LoteResponse.model_validate(f.lote),
            sucursal_id=f.sucursal_id,
            cantidad=f.cantidad,
            dias_para_vencer=f.dias_para_vencer,
        )
        for f in filas
    ])


@router.get("/lotes/{lote_id}", response_model=ApiResponse[LoteResponse])
async def obtener_lote(
    lote_id: UUID,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("inventario.leer")),
):
    try:
        lote = await ObtenerLoteUseCase(lote_repo(db)).ejecutar(lote_id)
    except Exception as e:
        raise traducir(e)
    return ok(lote)


@router.patch("/lotes/{lote_id}", response_model=ApiResponse[LoteResponse])
async def actualizar_lote(
    lote_id: UUID,
    body: ActualizarLoteRequest,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("inventario.editar")),
):
    try:
        lote = await ActualizarLoteUseCase(lote_repo(db)).ejecutar(ActualizarLoteInput(
            lote_id=lote_id,
            codigo_lote=body.codigo_lote,
            costo=body.costo,
            fecha_caducidad=body.fecha_caducidad,
            cambiar_fecha_caducidad=body.cambiar_fecha_caducidad,
            proveedor=body.proveedor,
            cambiar_proveedor=body.cambiar_proveedor,
        ))
    except Exception as e:
        raise traducir(e)
    return ok(lote)


@router.patch(
    "/lotes/{lote_id}/desactivar", response_model=ApiResponse[dict],
)
async def desactivar_lote(
    lote_id: UUID,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("inventario.editar")),
):
    try:
        await DesactivarLoteUseCase(lote_repo(db)).ejecutar(lote_id)
    except Exception as e:
        raise traducir(e)
    return ok({"status": "ok"})


@router.get(
    "/productos/{producto_id}/lotes", response_model=ApiResponse[list[LoteResponse]],
)
async def listar_lotes_producto(
    producto_id: UUID,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("inventario.leer")),
    incluir_inactivos: bool = Query(default=False),
):
    try:
        lotes = await ListarLotesUseCase(lote_repo(db), prod_repo(db)).ejecutar(
            producto_id, incluir_inactivos,
        )
    except Exception as e:
        raise traducir(e)
    return ok(lotes)


@router.post(
    "/productos/{producto_id}/lotes", response_model=ApiResponse[LoteResponse],
    status_code=status.HTTP_201_CREATED,
)
async def crear_lote_producto(
    producto_id: UUID,
    body: CrearLoteRequest,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("inventario.editar")),
):
    try:
        lote = await CrearLoteUseCase(lote_repo(db), prod_repo(db)).ejecutar(CrearLoteInput(
            producto_id=producto_id,
            codigo_lote=body.codigo_lote,
            costo=body.costo,
            fecha_caducidad=body.fecha_caducidad,
            proveedor=body.proveedor,
        ))
    except Exception as e:
        raise traducir(e)
    return ok(lote)
