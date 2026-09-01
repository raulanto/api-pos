from uuid import UUID

from app.modules.usuarios.domain.entities import Usuario
from app.modules.usuarios.domain.exceptions import UsuarioNoEncontrado
from app.modules.usuarios.application.ports.usuario_repository import UsuarioRepository


class ObtenerUsuarioUseCase:
    def __init__(self, usuario_repo: UsuarioRepository):
        self._usuario_repo = usuario_repo

    async def ejecutar(
        self, usuario_id: UUID, includes: frozenset[str] = frozenset()
    ) -> Usuario:
        usuario = await self._usuario_repo.obtener_por_id(usuario_id, includes)
        if usuario is None:
            raise UsuarioNoEncontrado(f"No existe usuario con id {usuario_id}")
        return usuario
