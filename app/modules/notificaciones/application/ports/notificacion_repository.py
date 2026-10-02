from abc import ABC, abstractmethod
from uuid import UUID
from typing import Sequence
from app.modules.notificaciones.domain.entities import Notificacion


class NotificacionRepository(ABC):
    @abstractmethod
    async def guardar(self, notificacion: Notificacion) -> Notificacion: ...

    @abstractmethod
    async def guardar_varias(self, notificaciones: list[Notificacion]) -> list[Notificacion]: ...

    @abstractmethod
    async def obtener_por_id(self, notificacion_id: UUID) -> Notificacion | None: ...

    @abstractmethod
    async def listar_por_usuario(
        self,
        usuario_id: UUID,
        leida: bool | None = None,
        modulo: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[Sequence[Notificacion], int]: ...

    @abstractmethod
    async def contar_no_leidas(self, usuario_id: UUID) -> int: ...

    @abstractmethod
    async def marcar_todas_como_leidas(self, usuario_id: UUID) -> int: ...
