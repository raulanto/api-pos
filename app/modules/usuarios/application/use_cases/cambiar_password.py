from dataclasses import dataclass
from uuid import UUID

from app.modules.usuarios.domain.exceptions import (
    UsuarioNoEncontrado, CredencialesInvalidas,
)
from app.modules.usuarios.domain.password_policy import validar_password
from app.modules.usuarios.application.ports.usuario_repository import UsuarioRepository
from app.modules.usuarios.application.ports.refresh_token_repository import RefreshTokenRepository
from app.core.security import verify_password, get_password_hash


@dataclass
class CambiarPasswordInput:
    usuario_id: UUID          # a quién se le cambia
    solicitante_id: UUID      # quién lo pide
    password_actual: str | None
    password_nueva: str
    solicitante_es_gestor: bool = False   # tiene usuarios.editar y actúa sobre otro


class CambiarPasswordUseCase:
    def __init__(
        self,
        usuario_repo: UsuarioRepository,
        refresh_token_repo: RefreshTokenRepository,
    ):
        self._usuario_repo = usuario_repo
        self._refresh_token_repo = refresh_token_repo

    async def ejecutar(self, data: CambiarPasswordInput) -> None:
        usuario = await self._usuario_repo.obtener_por_id(data.usuario_id)
        if usuario is None:
            raise UsuarioNoEncontrado(f"No existe usuario con id {data.usuario_id}")

        es_propia = data.usuario_id == data.solicitante_id
        if es_propia or not data.solicitante_es_gestor:
            # Cambiar la propia contraseña exige la actual.
            if not data.password_actual or not verify_password(data.password_actual, usuario.password_hash):
                raise CredencialesInvalidas("La contraseña actual es incorrecta")

        validar_password(data.password_nueva, usuario.email)

        usuario.password_hash = get_password_hash(data.password_nueva)
        await self._usuario_repo.guardar(usuario)

        # Al cambiar la contraseña se cierran las demás sesiones del usuario.
        await self._refresh_token_repo.revocar_todos_del_usuario(usuario.id)
