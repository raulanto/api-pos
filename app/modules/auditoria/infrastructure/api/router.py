from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_permission, UsuarioAutenticado
from app.shared.responses import (
    ApiResponse, EnvelopeRoute, PageParams, Sort,
    page_params, make_sort_dependency, make_include_dependency, ok, page_response,
)
from app.shared.filtering import active_filters
from app.modules.auditoria.application.dtos import FiltroAuditoria
from app.modules.auditoria.application.use_cases.listar_auditoria import (
    ListarAuditoriaUseCase, ObtenerLogAuditoriaUseCase, LogNoEncontrado,
)
from app.modules.auditoria.infrastructure.persistence.auditoria_repository_impl import (
    SqlAlchemyAuditoriaRepository,
)
from app.modules.auditoria.infrastructure.api.schemas import LogAuditoriaResponse

router = APIRouter(route_class=EnvelopeRoute)

_ORDEN_AUDITORIA = make_sort_dependency({"fecha", "modulo", "accion"}, "fecha:desc")
_INC_AUDITORIA = make_include_dependency({"usuario"})


def _repo(db: AsyncSession) -> SqlAlchemyAuditoriaRepository:
    return SqlAlchemyAuditoriaRepository(db)


@router.get("", response_model=ApiResponse[list[LogAuditoriaResponse]])
async def listar_auditoria(
    request: Request,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("auditoria.leer")),
    usuario_id: UUID | None = Query(default=None),
    modulo: str | None = Query(default=None),
    accion: str | None = Query(default=None),
    entidad: str | None = Query(default=None),
    entidad_id: str | None = Query(default=None),
    desde: datetime | None = Query(default=None),
    hasta: datetime | None = Query(default=None),
    paginacion: PageParams = Depends(page_params),
    orden: Sort = Depends(_ORDEN_AUDITORIA),
    include: frozenset[str] = Depends(_INC_AUDITORIA),
):
    filtro = FiltroAuditoria(
        usuario_id=usuario_id, modulo=modulo, accion=accion,
        entidad=entidad, entidad_id=entidad_id, desde=desde, hasta=hasta,
    )
    pagina = await ListarAuditoriaUseCase(_repo(db)).ejecutar(filtro, paginacion, orden, include)
    return page_response(
        request, pagina, paginacion, sort=orden, filters=active_filters(filtro),
    )


@router.get("/{log_id}", response_model=ApiResponse[LogAuditoriaResponse])
async def obtener_log(
    log_id: UUID,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("auditoria.leer")),
    include: frozenset[str] = Depends(_INC_AUDITORIA),
):
    try:
        log = await ObtenerLogAuditoriaUseCase(_repo(db)).ejecutar(log_id, include)
    except LogNoEncontrado as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(e))
    return ok(log)
