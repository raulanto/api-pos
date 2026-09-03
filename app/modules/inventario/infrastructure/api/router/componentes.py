from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_permission, UsuarioAutenticado
from app.shared.responses import (
    ApiResponse, EnvelopeRoute, make_include_dependency, ok,
)
from app.modules.inventario.application.use_cases.gestionar_componentes import (
    ListarComponentesUseCase,
    AgregarComponenteUseCase, AgregarComponenteInput,
    ActualizarComponenteUseCase, ActualizarComponenteInput,
    QuitarComponenteUseCase,
    ReemplazarRecetaUseCase, ReemplazarRecetaInput, LineaRecetaInput,
)
from app.modules.inventario.infrastructure.api.schemas import (
    AgregarComponenteRequest, ActualizarComponenteRequest, ReemplazarRecetaRequest,
    ComponenteResponse,
)
from .common import comp_repo, prod_repo, traducir

router = APIRouter(route_class=EnvelopeRoute)

_INC_COMP = make_include_dependency({"producto"})


@router.get(
    "/productos/{kit_id}/componentes",
    response_model=ApiResponse[list[ComponenteResponse]],
)
async def listar_componentes(
    kit_id: UUID,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("inventario.leer")),
    include: frozenset[str] = Depends(_INC_COMP),
):
    try:
        lineas = await ListarComponentesUseCase(comp_repo(db), prod_repo(db)).ejecutar(
            kit_id, include,
        )
    except Exception as e:
        raise traducir(e)
    return ok(lineas)


@router.put(
    "/productos/{kit_id}/componentes",
    response_model=ApiResponse[list[ComponenteResponse]],
)
async def reemplazar_receta(
    kit_id: UUID,
    body: ReemplazarRecetaRequest,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("inventario.editar")),
):
    try:
        lineas = await ReemplazarRecetaUseCase(comp_repo(db), prod_repo(db)).ejecutar(
            ReemplazarRecetaInput(
                kit_id=kit_id,
                componentes=[
                    LineaRecetaInput(
                        producto_componente_id=c.producto_componente_id, cantidad=c.cantidad,
                    )
                    for c in body.componentes
                ],
            )
        )
    except Exception as e:
        raise traducir(e)
    return ok(lineas)


@router.post(
    "/productos/{kit_id}/componentes",
    response_model=ApiResponse[ComponenteResponse],
    status_code=status.HTTP_201_CREATED,
)
async def agregar_componente(
    kit_id: UUID,
    body: AgregarComponenteRequest,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("inventario.editar")),
):
    try:
        linea = await AgregarComponenteUseCase(comp_repo(db), prod_repo(db)).ejecutar(
            AgregarComponenteInput(
                kit_id=kit_id,
                producto_componente_id=body.producto_componente_id,
                cantidad=body.cantidad,
            )
        )
    except Exception as e:
        raise traducir(e)
    return ok(linea)


@router.patch(
    "/productos/{kit_id}/componentes/{componente_id}",
    response_model=ApiResponse[ComponenteResponse],
)
async def actualizar_componente(
    kit_id: UUID,
    componente_id: UUID,
    body: ActualizarComponenteRequest,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("inventario.editar")),
):
    try:
        linea = await ActualizarComponenteUseCase(comp_repo(db), prod_repo(db)).ejecutar(
            ActualizarComponenteInput(
                kit_id=kit_id,
                producto_componente_id=componente_id,
                cantidad=body.cantidad,
            )
        )
    except Exception as e:
        raise traducir(e)
    return ok(linea)


@router.delete(
    "/productos/{kit_id}/componentes/{componente_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def quitar_componente(
    kit_id: UUID,
    componente_id: UUID,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("inventario.editar")),
):
    try:
        await QuitarComponenteUseCase(comp_repo(db), prod_repo(db)).ejecutar(
            kit_id, componente_id,
        )
    except Exception as e:
        raise traducir(e)
