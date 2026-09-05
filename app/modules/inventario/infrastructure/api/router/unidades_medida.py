from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_permission, UsuarioAutenticado
from app.shared.responses import ApiResponse, EnvelopeRoute, ok
from app.modules.inventario.application.use_cases.gestionar_unidades_medida import (
    ListarUnidadesMedidaUseCase, ObtenerUnidadMedidaUseCase,
    CrearUnidadMedidaUseCase, CrearUnidadMedidaInput,
    ActualizarUnidadMedidaUseCase, ActualizarUnidadMedidaInput,
    DesactivarUnidadMedidaUseCase, ReactivarUnidadMedidaUseCase,
)
from app.modules.inventario.infrastructure.api.schemas import (
    CrearUnidadMedidaRequest, ActualizarUnidadMedidaRequest, UnidadMedidaResponse,
)
from .common import um_repo, traducir

router = APIRouter(route_class=EnvelopeRoute)


@router.get(
    "/unidades-medida", response_model=ApiResponse[list[UnidadMedidaResponse]],
)
async def listar_unidades_medida(
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("inventario.leer")),
    incluir_inactivas: bool = Query(default=False),
):
    unidades = await ListarUnidadesMedidaUseCase(um_repo(db)).ejecutar(incluir_inactivas)
    return ok(unidades)


@router.post(
    "/unidades-medida", response_model=ApiResponse[UnidadMedidaResponse],
    status_code=status.HTTP_201_CREATED,
)
async def crear_unidad_medida(
    body: CrearUnidadMedidaRequest,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("inventario.crear")),
):
    try:
        unidad = await CrearUnidadMedidaUseCase(um_repo(db)).ejecutar(
            CrearUnidadMedidaInput(
                codigo=body.codigo,
                nombre=body.nombre,
                tipo_magnitud=body.tipo_magnitud,
                decimales=body.decimales,
            )
        )
    except Exception as e:
        raise traducir(e)
    return ok(unidad)


@router.get(
    "/unidades-medida/{unidad_id}", response_model=ApiResponse[UnidadMedidaResponse],
)
async def obtener_unidad_medida(
    unidad_id: UUID,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("inventario.leer")),
):
    try:
        unidad = await ObtenerUnidadMedidaUseCase(um_repo(db)).ejecutar(unidad_id)
    except Exception as e:
        raise traducir(e)
    return ok(unidad)


@router.patch(
    "/unidades-medida/{unidad_id}", response_model=ApiResponse[UnidadMedidaResponse],
)
async def actualizar_unidad_medida(
    unidad_id: UUID,
    body: ActualizarUnidadMedidaRequest,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("inventario.editar")),
):
    try:
        unidad = await ActualizarUnidadMedidaUseCase(um_repo(db)).ejecutar(
            ActualizarUnidadMedidaInput(
                unidad_id=unidad_id,
                nombre=body.nombre,
                tipo_magnitud=body.tipo_magnitud,
                decimales=body.decimales,
            )
        )
    except Exception as e:
        raise traducir(e)
    return ok(unidad)


@router.patch(
    "/unidades-medida/{unidad_id}/desactivar",
    response_model=ApiResponse[dict],
)
async def desactivar_unidad_medida(
    unidad_id: UUID,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("inventario.editar")),
):
    try:
        await DesactivarUnidadMedidaUseCase(um_repo(db)).ejecutar(unidad_id)
    except Exception as e:
        raise traducir(e)
    return ok({"status": "ok"})


@router.patch(
    "/unidades-medida/{unidad_id}/reactivar",
    response_model=ApiResponse[UnidadMedidaResponse],
)
async def reactivar_unidad_medida(
    unidad_id: UUID,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("inventario.editar")),
):
    try:
        unidad = await ReactivarUnidadMedidaUseCase(um_repo(db)).ejecutar(unidad_id)
    except Exception as e:
        raise traducir(e)
    return ok(unidad)
