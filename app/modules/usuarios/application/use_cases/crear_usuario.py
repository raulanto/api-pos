from dataclasses import dataclass
from uuid import UUID
from app.modules.usuarios.domain.entities import Usuario
from app.modules.usuarios.domain.exceptions import RolNoEncontrado, SucursalNoEncontrada, EmailDuplicado
from app.modules.usuarios.application.ports.usuario_repository import UsuarioRepository
from app.modules.usuarios.application.ports.catalogos_repository import RolRepository, SucursalRepository
from app.modules.usuarios.domain.password_policy import validar_password
from app.core.security import get_password_hash

@dataclass
class CrearUsuarioInput:
    sucursal_id: UUID | None
    rol_id: UUID
    nombre: str
    email: str
    password_plano: str

class CrearUsuarioUseCase:
    def __init__(
        self,
        usuario_repo: UsuarioRepository,
        rol_repo: RolRepository,
        sucursal_repo: SucursalRepository
    ):
        self._usuario_repo = usuario_repo
        self._rol_repo = rol_repo
        self._sucursal_repo = sucursal_repo

    async def ejecutar(self, data: CrearUsuarioInput) -> Usuario:
        validar_password(data.password_plano, data.email)

        # Validate Rol
        rol = await self._rol_repo.obtener_por_id(data.rol_id)
        if not rol:
            raise RolNoEncontrado(f"No existe rol con id {data.rol_id}")

        # Validate Sucursal if provided
        if data.sucursal_id:
            sucursal = await self._sucursal_repo.obtener_por_id(data.sucursal_id)
            if not sucursal:
                raise SucursalNoEncontrada(f"No existe sucursal con id {data.sucursal_id}")

        # Validate Email Uniqueness
        existente = await self._usuario_repo.obtener_por_email(data.email)
        if existente:
            raise EmailDuplicado("El email ya está en uso")

        password_hash = get_password_hash(data.password_plano)
        usuario = Usuario.crear(
            sucursal_id=data.sucursal_id,
            rol_id=data.rol_id,
            nombre=data.nombre,
            email=data.email,
            password_hash=password_hash,
        )

        await self._usuario_repo.guardar(usuario)
        return usuario
