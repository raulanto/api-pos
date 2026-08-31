from dataclasses import dataclass
from datetime import datetime, timezone

from app.modules.usuarios.domain.exceptions import CredencialesInvalidas
from app.modules.usuarios.domain.entities import RefreshToken
from app.modules.usuarios.application.ports.usuario_repository import UsuarioRepository
from app.modules.usuarios.application.ports.catalogos_repository import RolRepository
from app.modules.usuarios.application.ports.refresh_token_repository import RefreshTokenRepository
from app.core.security import (
    verify_password, create_access_token,
    generate_refresh_token, hash_refresh_token, refresh_token_expiry,
)


@dataclass
class AutenticarUsuarioInput:
    email: str
    password_plano: str
    user_agent: str | None = None
    ip: str | None = None


@dataclass
class TokenOutput:
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class AutenticarUsuarioUseCase:
    def __init__(
        self,
        usuario_repo: UsuarioRepository,
        rol_repo: RolRepository,
        refresh_token_repo: RefreshTokenRepository,
    ):
        self._usuario_repo = usuario_repo
        self._rol_repo = rol_repo
        self._refresh_token_repo = refresh_token_repo

    async def ejecutar(self, data: AutenticarUsuarioInput) -> TokenOutput:
        usuario = await self._usuario_repo.obtener_por_email(data.email)
        if not usuario or not usuario.activo:
            raise CredencialesInvalidas("Email o contraseña incorrectos")

        if not verify_password(data.password_plano, usuario.password_hash):
            raise CredencialesInvalidas("Email o contraseña incorrectos")

        usuario.last_login_at = datetime.now(timezone.utc)
        await self._usuario_repo.guardar(usuario)

        rol = await self._rol_repo.obtener_por_id(usuario.rol_id)
        rol_codigo = rol.codigo if rol else None

        access_token = create_access_token(data={"sub": str(usuario.id), "rol": rol_codigo})

        refresh_plano = generate_refresh_token()
        await self._refresh_token_repo.guardar(RefreshToken.crear(
            usuario_id=usuario.id,
            token_hash=hash_refresh_token(refresh_plano),
            expira_en=refresh_token_expiry(),
            user_agent=data.user_agent,
            ip=data.ip,
        ))

        return TokenOutput(access_token=access_token, refresh_token=refresh_plano)
