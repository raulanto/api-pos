from dataclasses import dataclass
from uuid import UUID

from app.modules.usuarios.domain.entities import Usuario
from app.modules.usuarios.domain.exceptions import (
    UsuarioNoEncontrado, SucursalNoEncontrada, EmailDuplicado,
)
from app.modules.usuarios.application.ports.usuario_repository import UsuarioRepository
from app.modules.usuarios.application.ports.catalogos_repository import SucursalRepository


@dataclass
class EditarUsuarioInput:
    usuario_id: UUID
    nombre: str | None = None
    email: str | None = None
    sucursal_id: UUID | None = None
    _sucursal_presente: bool = False   # distinguir "no tocar" de "poner en null"


class EditarUsuarioUseCase:
    """
    Edita datos básicos: nombre, email y sucursal. NO cambia el rol
    (eso es cambiar_rol_usuario, que exige el permiso roles.gestionar).
    """

    def __init__(self, usuario_repo: UsuarioRepository, sucursal_repo: SucursalRepository):
        self._usuario_repo = usuario_repo
        self._sucursal_repo = sucursal_repo

    async def ejecutar(self, data: EditarUsuarioInput) -> Usuario:
        usuario = await self._usuario_repo.obtener_por_id(data.usuario_id)
        if usuario is None:
            raise UsuarioNoEncontrado(f"No existe usuario con id {data.usuario_id}")

        if data.nombre is not None:
            usuario.nombre = data.nombre

        if data.email is not None and data.email != usuario.email:
            existente = await self._usuario_repo.obtener_por_email(data.email)
            if existente and existente.id != usuario.id:
                raise EmailDuplicado("El email ya está en uso")
            usuario.email = data.email

        if data._sucursal_presente:
            if data.sucursal_id is not None:
                sucursal = await self._sucursal_repo.obtener_por_id(data.sucursal_id)
                if not sucursal:
                    raise SucursalNoEncontrada(f"No existe sucursal con id {data.sucursal_id}")
            usuario.sucursal_id = data.sucursal_id

        await self._usuario_repo.guardar(usuario)
        return usuario
