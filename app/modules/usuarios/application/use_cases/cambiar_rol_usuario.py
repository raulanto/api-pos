from dataclasses import dataclass
from uuid import UUID

from app.modules.usuarios.domain.entities import Usuario, ROL_ADMIN
from app.modules.usuarios.domain.exceptions import (
    UsuarioNoEncontrado, RolNoEncontrado, UltimoAdminActivo,
)
from app.modules.usuarios.application.ports.usuario_repository import UsuarioRepository
from app.modules.usuarios.application.ports.catalogos_repository import RolRepository


@dataclass
class CambiarRolUsuarioInput:
    usuario_id: UUID
    nuevo_rol_id: UUID


class CambiarRolUsuarioUseCase:
    """Requiere el permiso roles.gestionar (se valida en el router)."""

    def __init__(self, usuario_repo: UsuarioRepository, rol_repo: RolRepository):
        self._usuario_repo = usuario_repo
        self._rol_repo = rol_repo

    async def ejecutar(self, data: CambiarRolUsuarioInput) -> Usuario:
        usuario = await self._usuario_repo.obtener_por_id(data.usuario_id)
        if usuario is None:
            raise UsuarioNoEncontrado(f"No existe usuario con id {data.usuario_id}")

        nuevo_rol = await self._rol_repo.obtener_por_id(data.nuevo_rol_id)
        if nuevo_rol is None:
            raise RolNoEncontrado(f"No existe rol con id {data.nuevo_rol_id}")

        rol_actual = await self._rol_repo.obtener_por_id(usuario.rol_id)
        saca_admin = (
            rol_actual is not None
            and rol_actual.codigo == ROL_ADMIN
            and nuevo_rol.codigo != ROL_ADMIN
        )
        if saca_admin and usuario.activo:
            if await self._usuario_repo.contar_admins_activos(excluir_usuario_id=usuario.id) == 0:
                raise UltimoAdminActivo("No se puede quitar el rol admin al último administrador activo")

        usuario.rol_id = data.nuevo_rol_id
        await self._usuario_repo.guardar(usuario)
        return usuario
