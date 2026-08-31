from abc import ABC, abstractmethod
from uuid import UUID
from app.modules.usuarios.domain.entities import Usuario


class UsuarioRepository(ABC):
    @abstractmethod
    async def guardar(self, usuario: Usuario) -> None: ...

    @abstractmethod
    async def obtener_por_id(self, usuario_id: UUID) -> Usuario | None: ...

    @abstractmethod
    async def obtener_por_email(self, email: str) -> Usuario | None: ...

    @abstractmethod
    async def listar(self, sucursal_id: UUID | None = None, incluir_inactivos: bool = True) -> list[Usuario]: ...

    @abstractmethod
    async def contar_admins_activos(self, excluir_usuario_id: UUID | None = None) -> int:
        """Cuenta usuarios activos cuyo rol tiene codigo 'admin'."""
        ...
