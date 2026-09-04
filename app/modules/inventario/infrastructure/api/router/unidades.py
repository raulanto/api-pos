from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_permission, UsuarioAutenticado
from app.shared.responses import ApiResponse, EnvelopeRoute, ok
from app.modules.inventario.application.use_cases.gestionar_unidades import (
    ListarUnidadesUseCase,
    AgregarUnidadUseCase, AgregarUnidadInput,
    ActualizarUnidadUseCase, ActualizarUnidadInput,
    DesactivarUnidadUseCase,
    ResolverCodigoBarrasUseCase,
)
from app.modules.inventario.infrastructure.api.schemas import (
    AgregarUnidadRequest, ActualizarUnidadRequest, UnidadResponse, ResolucionCodigoResponse,
)
from .common import unidad_repo, prod_repo, traducir

router = APIRouter(route_class=EnvelopeRoute)


@router.get(
    "/productos/resolver-codigo", response_model=ApiResponse[ResolucionCodigoResponse],
)
async def resolver_codigo_barras(
    codigo_barras: str = Query(min_length=1),
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("inventario.leer")),
):
    """Escaneo POS: devuelve el producto, la presentación (si aplica), el `factor`
    y el `precio_venta` a usar en la línea de venta."""
    try:
        res = await ResolverCodigoBarrasUseCase(unidad_repo(db), prod_repo(db)).ejecutar(
            codigo_barras,
        )
    except Exception as e:
        raise traducir(e)
    return ok(res)


@router.get(
    "/productos/{producto_id}/unidades", response_model=ApiResponse[list[UnidadResponse]],
)
async def listar_unidades(
    producto_id: UUID,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("inventario.leer")),
    incluir_inactivas: bool = Query(default=False),
):
    try:
        unidades = await ListarUnidadesUseCase(unidad_repo(db), prod_repo(db)).ejecutar(
            producto_id, incluir_inactivas,
        )
    except Exception as e:
        raise traducir(e)
    return ok(unidades)


@router.post(
    "/productos/{producto_id}/unidades",
    response_model=ApiResponse[UnidadResponse],
    status_code=status.HTTP_201_CREATED,
)
async def agregar_unidad(
    producto_id: UUID,
    body: AgregarUnidadRequest,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("inventario.editar")),
):
    try:
        unidad = await AgregarUnidadUseCase(unidad_repo(db), prod_repo(db)).ejecutar(
            AgregarUnidadInput(
                producto_id=producto_id,
                nombre=body.nombre,
                unidad_medida=body.unidad_medida,
                precio_venta=body.precio_venta,
                factor=body.factor,
                unidades_por_base=body.unidades_por_base,
                codigo_barras=body.codigo_barras,
            )
        )
    except Exception as e:
        raise traducir(e)
    return ok(unidad)


@router.patch(
    "/productos/{producto_id}/unidades/{unidad_id}",
    response_model=ApiResponse[UnidadResponse],
)
async def actualizar_unidad(
    producto_id: UUID,
    unidad_id: UUID,
    body: ActualizarUnidadRequest,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("inventario.editar")),
):
    try:
        unidad = await ActualizarUnidadUseCase(unidad_repo(db), prod_repo(db)).ejecutar(
            ActualizarUnidadInput(
                producto_id=producto_id,
                unidad_id=unidad_id,
                nombre=body.nombre,
                unidad_medida=body.unidad_medida,
                factor=body.factor,
                unidades_por_base=body.unidades_por_base,
                precio_venta=body.precio_venta,
                codigo_barras=body.codigo_barras,
                cambiar_codigo_barras=body.cambiar_codigo_barras,
            )
        )
    except Exception as e:
        raise traducir(e)
    return ok(unidad)


@router.delete(
    "/productos/{producto_id}/unidades/{unidad_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def desactivar_unidad(
    producto_id: UUID,
    unidad_id: UUID,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("inventario.editar")),
):
    try:
        await DesactivarUnidadUseCase(unidad_repo(db), prod_repo(db)).ejecutar(
            producto_id, unidad_id,
        )
    except Exception as e:
        raise traducir(e)
