from dataclasses import dataclass
from uuid import UUID

from app.modules.usuarios.application.ports.usuario_repository import UsuarioRepository
from app.shared.responses import Page, PageParams, Sort


@dataclass
class ListarUsuariosInput:
    sucursal_id: UUID | None = None      # None => todas las sucursales
    incluir_inactivos: bool = True


class ListarUsuariosUseCase:
    def __init__(self, usuario_repo: UsuarioRepository):
        self._usuario_repo = usuario_repo

    async def ejecutar(
        self,
        data: ListarUsuariosInput,
        paginacion: PageParams,
        orden: Sort,
        includes: frozenset[str] = frozenset(),
    ) -> Page:
        return await self._usuario_repo.listar(
            paginacion=paginacion,
            orden=orden,
            sucursal_id=data.sucursal_id,
            incluir_inactivos=data.incluir_inactivos,
            includes=includes,
        )
