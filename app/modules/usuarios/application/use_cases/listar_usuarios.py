from dataclasses import dataclass
from uuid import UUID

from app.modules.usuarios.domain.entities import Usuario
from app.modules.usuarios.application.ports.usuario_repository import UsuarioRepository


@dataclass
class ListarUsuariosInput:
    sucursal_id: UUID | None = None      # None => todas las sucursales
    incluir_inactivos: bool = True


class ListarUsuariosUseCase:
    def __init__(self, usuario_repo: UsuarioRepository):
        self._usuario_repo = usuario_repo

    async def ejecutar(self, data: ListarUsuariosInput) -> list[Usuario]:
        return await self._usuario_repo.listar(
            sucursal_id=data.sucursal_id,
            incluir_inactivos=data.incluir_inactivos,
        )
