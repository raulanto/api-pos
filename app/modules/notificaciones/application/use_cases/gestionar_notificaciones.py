from dataclasses import dataclass
from uuid import UUID
from app.modules.notificaciones.domain.entities import Notificacion
from app.modules.notificaciones.domain.exceptions import NotificacionNoEncontrada, AccesoDenegadoNotificacion
from app.modules.notificaciones.application.ports.notificacion_repository import NotificacionRepository


@dataclass
class NotificacionFiltrosInput:
    usuario_id: UUID
    leida: bool | None = None
    modulo: str | None = None
    page: int = 1
    page_size: int = 20


class NotificacionesUseCase:
    def __init__(self, notificacion_repo: NotificacionRepository):
        self._repo = notificacion_repo

    async def listar(self, filtros: NotificacionFiltrosInput) -> tuple[list[Notificacion], int]:
        items, total = await self._repo.listar_por_usuario(
            usuario_id=filtros.usuario_id,
            leida=filtros.leida,
            modulo=filtros.modulo,
            page=filtros.page,
            page_size=filtros.page_size,
        )
        return list(items), total

    async def contar_no_leidas(self, usuario_id: UUID) -> int:
        return await self._repo.contar_no_leidas(usuario_id)

    async def marcar_como_leida(self, notificacion_id: UUID, usuario_id: UUID) -> Notificacion:
        notificacion = await self._repo.obtener_por_id(notificacion_id)
        if not notificacion:
            raise NotificacionNoEncontrada(f"No se encontró la notificación {notificacion_id}")
        if notificacion.usuario_id != usuario_id:
            raise AccesoDenegadoNotificacion("No tienes permiso para modificar esta notificación")

        notificacion.marcar_como_leida()
        return await self._repo.guardar(notificacion)

    async def marcar_todas_como_leidas(self, usuario_id: UUID) -> int:
        return await self._repo.marcar_todas_como_leidas(usuario_id)
