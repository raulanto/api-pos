from abc import ABC, abstractmethod
from uuid import UUID
from app.modules.usuarios.domain.entities import RefreshToken


class RefreshTokenRepository(ABC):
    @abstractmethod
    async def guardar(self, token: RefreshToken) -> None: ...

    @abstractmethod
    async def obtener_por_hash(self, token_hash: str) -> RefreshToken | None: ...

    @abstractmethod
    async def revocar(self, token_id: UUID) -> None: ...

    @abstractmethod
    async def revocar_todos_del_usuario(self, usuario_id: UUID) -> None: ...
