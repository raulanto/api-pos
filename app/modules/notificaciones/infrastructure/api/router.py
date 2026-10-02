from fastapi import APIRouter, Depends, Query, HTTPException, status
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.shared.responses import ok, ApiResponse
from app.modules.usuarios.infrastructure.persistence.orm_models import UsuarioORM
from app.modules.notificaciones.domain.exceptions import NotificacionNoEncontrada, AccesoDenegadoNotificacion
from app.modules.notificaciones.application.use_cases.gestionar_notificaciones import (
    NotificacionesUseCase,
    NotificacionFiltrosInput,
)
from app.modules.notificaciones.infrastructure.persistence.notificacion_repository_impl import NotificacionRepositoryImpl
from app.modules.notificaciones.infrastructure.api.schemas import NotificacionOut, ResumenNotificacionesOut

router = APIRouter()


def _get_service(db: AsyncSession = Depends(get_db)) -> NotificacionesUseCase:
    repo = NotificacionRepositoryImpl(db)
    return NotificacionesUseCase(repo)


@router.get("", response_model=ApiResponse)
async def listar_notificaciones(
    leida: bool | None = Query(None, description="Filtrar por leídas (True) o no leídas (False)"),
    modulo: str | None = Query(None, description="Filtrar por módulo origen"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: UsuarioORM = Depends(get_current_user),
    service: NotificacionesUseCase = Depends(_get_service),
):
    filtros = NotificacionFiltrosInput(
        usuario_id=current_user.id,
        leida=leida,
        modulo=modulo,
        page=page,
        page_size=page_size,
    )
    items, total = await service.listar(filtros)
    total_pages = max(1, (total + page_size - 1) // page_size) if total > 0 else 1
    data = [NotificacionOut.model_validate(item).model_dump(mode="json") for item in items]

    meta = {
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total_items": total,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_prev": page > 1,
        }
    }
    return ok(data, meta=meta)


@router.get("/resumen", response_model=ApiResponse)
async def obtener_resumen_notificaciones(
    current_user: UsuarioORM = Depends(get_current_user),
    service: NotificacionesUseCase = Depends(_get_service),
):
    count = await service.contar_no_leidas(current_user.id)
    return ok(ResumenNotificacionesOut(unread_count=count).model_dump(mode="json"))


@router.patch("/{notificacion_id}/marcar-leida", response_model=ApiResponse)
async def marcar_notificacion_leida(
    notificacion_id: UUID,
    current_user: UsuarioORM = Depends(get_current_user),
    service: NotificacionesUseCase = Depends(_get_service),
):
    try:
        notificacion = await service.marcar_como_leida(notificacion_id, current_user.id)
        return ok(NotificacionOut.model_validate(notificacion).model_dump(mode="json"))
    except NotificacionNoEncontrada as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except AccesoDenegadoNotificacion as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@router.patch("/marcar-todas-leidas", response_model=ApiResponse)
async def marcar_todas_notificaciones_leidas(
    current_user: UsuarioORM = Depends(get_current_user),
    service: NotificacionesUseCase = Depends(_get_service),
):
    count = await service.marcar_todas_como_leidas(current_user.id)
    return ok({"message": f"{count} notificaciones marcadas como leídas", "count": count})
