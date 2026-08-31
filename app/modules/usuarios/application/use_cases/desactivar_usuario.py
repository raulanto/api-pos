from dataclasses import dataclass
from uuid import UUID

from app.modules.usuarios.domain.entities import Usuario, ROL_ADMIN
from app.modules.usuarios.domain.exceptions import (
    UsuarioNoEncontrado, UltimoAdminActivo, AutoDesactivacionNoPermitida,
)
from app.modules.usuarios.application.ports.usuario_repository import UsuarioRepository
from app.modules.usuarios.application.ports.catalogos_repository import RolRepository


@dataclass
class DesactivarUsuarioInput:
    usuario_id: UUID
    solicitante_id: UUID


class DesactivarUsuarioUseCase:
    def __init__(self, usuario_repo: UsuarioRepository, rol_repo: RolRepository):
        self._usuario_repo = usuario_repo
        self._rol_repo = rol_repo

    async def ejecutar(self, data: DesactivarUsuarioInput) -> Usuario:
        if data.usuario_id == data.solicitante_id:
            raise AutoDesactivacionNoPermitida("Un usuario no puede desactivarse a sí mismo")

        usuario = await self._usuario_repo.obtener_por_id(data.usuario_id)
        if usuario is None:
            raise UsuarioNoEncontrado(f"No existe usuario con id {data.usuario_id}")

        if not usuario.activo:
            return usuario  # idempotente

        rol = await self._rol_repo.obtener_por_id(usuario.rol_id)
        if rol is not None and rol.codigo == ROL_ADMIN:
            otros_admins = await self._usuario_repo.contar_admins_activos(excluir_usuario_id=usuario.id)
            if otros_admins == 0:
                raise UltimoAdminActivo("No se puede desactivar al último administrador activo")

        usuario.activo = False
        await self._usuario_repo.guardar(usuario)
        return usuario
