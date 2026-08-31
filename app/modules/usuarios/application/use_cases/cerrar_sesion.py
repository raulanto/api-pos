from dataclasses import dataclass

from app.modules.usuarios.application.ports.refresh_token_repository import RefreshTokenRepository
from app.core.security import hash_refresh_token


@dataclass
class CerrarSesionInput:
    refresh_token: str


class CerrarSesionUseCase:
    def __init__(self, refresh_token_repo: RefreshTokenRepository):
        self._refresh_token_repo = refresh_token_repo

    async def ejecutar(self, data: CerrarSesionInput) -> None:
        almacenado = await self._refresh_token_repo.obtener_por_hash(
            hash_refresh_token(data.refresh_token)
        )
        # Idempotente: si no existe o ya estaba revocado, no hay nada que hacer.
        if almacenado is not None and not almacenado.revocado:
            await self._refresh_token_repo.revocar(almacenado.id)
