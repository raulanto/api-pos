from uuid import UUID

from app.modules.usuarios.domain.entities import Usuario
from app.modules.usuarios.domain.exceptions import UsuarioNoEncontrado
from app.modules.usuarios.application.ports.usuario_repository import UsuarioRepository


class ReactivarUsuarioUseCase:
    """Contraparte de `DesactivarUsuarioUseCase`: vuelve a poner `activo = True`.

    No necesita las guardas de la baja (`UltimoAdminActivo`,
    `AutoDesactivacionNoPermitida`): reactivar solo suma un usuario activo, y
    quien llama está autenticado (o sea, ya activo). El email tiene índice único
    total, así que sigue reservado mientras el usuario está inactivo: no hay
    conflicto posible al reactivar.
    """

    def __init__(self, usuario_repo: UsuarioRepository):
        self._usuario_repo = usuario_repo

    async def ejecutar(self, usuario_id: UUID) -> Usuario:
        usuario = await self._usuario_repo.obtener_por_id(usuario_id)
        if usuario is None:
            raise UsuarioNoEncontrado(f"No existe usuario con id {usuario_id}")

        if usuario.activo:
            return usuario  # idempotente

        usuario.activo = True
        await self._usuario_repo.guardar(usuario)
        return usuario
