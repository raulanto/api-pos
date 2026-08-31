from dataclasses import dataclass
from datetime import datetime, timezone
from app.modules.usuarios.domain.entities import Usuario
from app.modules.usuarios.domain.exceptions import CredencialesInvalidas
from app.modules.usuarios.application.ports.usuario_repository import UsuarioRepository
from app.core.security import verify_password, create_access_token

@dataclass
class AutenticarUsuarioInput:
    email: str
    password_plano: str

@dataclass
class TokenOutput:
    access_token: str
    token_type: str = "bearer"

class AutenticarUsuarioUseCase:
    def __init__(self, usuario_repo: UsuarioRepository):
        self._usuario_repo = usuario_repo

    async def ejecutar(self, data: AutenticarUsuarioInput) -> TokenOutput:
        usuario = await self._usuario_repo.obtener_por_email(data.email)
        if not usuario or not usuario.activo:
            raise CredencialesInvalidas("Email o contraseña incorrectos")

        if not verify_password(data.password_plano, usuario.password_hash):
            raise CredencialesInvalidas("Email o contraseña incorrectos")

        # Update last login time
        usuario.last_login_at = datetime.now(timezone.utc)
        await self._usuario_repo.guardar(usuario)

        access_token = create_access_token(data={"sub": str(usuario.id)})
        return TokenOutput(access_token=access_token)
