from dataclasses import dataclass
from datetime import datetime, timezone

from app.modules.usuarios.domain.entities import RefreshToken
from app.modules.usuarios.domain.exceptions import RefreshTokenInvalido
from app.modules.usuarios.application.ports.usuario_repository import UsuarioRepository
from app.modules.usuarios.application.ports.catalogos_repository import RolRepository
from app.modules.usuarios.application.ports.refresh_token_repository import RefreshTokenRepository
from app.core.security import (
    create_access_token,
    generate_refresh_token, hash_refresh_token, refresh_token_expiry,
)


@dataclass
class RefrescarTokenInput:
    refresh_token: str
    user_agent: str | None = None
    ip: str | None = None


@dataclass
class TokenOutput:
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefrescarTokenUseCase:
    """
    Rotación con detección de reuso (sección 8.2 del plan):
    - Cada /refresh revoca el token usado y emite uno nuevo.
    - Si llega un token ya revocado => posible robo => se revocan TODOS los
      refresh tokens del usuario y se rechaza.
    """

    def __init__(
        self,
        refresh_token_repo: RefreshTokenRepository,
        usuario_repo: UsuarioRepository,
        rol_repo: RolRepository,
    ):
        self._refresh_token_repo = refresh_token_repo
        self._usuario_repo = usuario_repo
        self._rol_repo = rol_repo

    async def ejecutar(self, data: RefrescarTokenInput) -> TokenOutput:
        token_hash = hash_refresh_token(data.refresh_token)
        almacenado = await self._refresh_token_repo.obtener_por_hash(token_hash)

        if almacenado is None:
            raise RefreshTokenInvalido("Refresh token no reconocido")

        if almacenado.revocado:
            # Reuso de un token ya revocado: revocar toda la familia del usuario.
            await self._refresh_token_repo.revocar_todos_del_usuario(almacenado.usuario_id)
            raise RefreshTokenInvalido("Refresh token reutilizado; se cerraron todas las sesiones")

        ahora = datetime.now(timezone.utc)
        if not almacenado.esta_vigente(ahora):
            raise RefreshTokenInvalido("Refresh token expirado")

        usuario = await self._usuario_repo.obtener_por_id(almacenado.usuario_id)
        if usuario is None or not usuario.activo:
            await self._refresh_token_repo.revocar(almacenado.id)
            raise RefreshTokenInvalido("Usuario inválido o inactivo")

        # Rotación: revoca el usado, emite uno nuevo.
        await self._refresh_token_repo.revocar(almacenado.id)

        nuevo_plano = generate_refresh_token()
        await self._refresh_token_repo.guardar(RefreshToken.crear(
            usuario_id=usuario.id,
            token_hash=hash_refresh_token(nuevo_plano),
            expira_en=refresh_token_expiry(),
            user_agent=data.user_agent,
            ip=data.ip,
        ))

        rol = await self._rol_repo.obtener_por_id(usuario.rol_id)
        rol_codigo = rol.codigo if rol else None
        access_token = create_access_token(data={"sub": str(usuario.id), "rol": rol_codigo})

        return TokenOutput(access_token=access_token, refresh_token=nuevo_plano)
