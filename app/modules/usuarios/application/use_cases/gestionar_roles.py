"""Casos de uso del submódulo roles (sección 7 y 10 del plan).

Reglas de negocio implementadas:
- No se puede eliminar el rol `admin`.
- El `codigo` de un rol es inmutable una vez creado.
- No se puede asignar a un rol un permiso que no existe (validado contra catálogo).
- No se puede eliminar un rol que aún tiene usuarios asignados.
"""
from dataclasses import dataclass, field
from uuid import UUID, uuid4

from app.modules.usuarios.domain.entities import Rol, Permiso, ROL_ADMIN
from app.modules.usuarios.domain.exceptions import (
    RolNoEncontrado, RolAdminProtegido, CodigoRolDuplicado,
    PermisoNoEncontrado, UsuarioNoEncontrado,
)
from app.modules.usuarios.application.ports.catalogos_repository import (
    RolRepository, PermisoRepository,
)
from app.shared.responses import Page, PageParams, Sort


def _normalizar_codigo(codigo: str) -> str:
    return codigo.strip().lower()


# --------------------------------------------------------------------------- #
@dataclass
class CrearRolInput:
    codigo: str
    nombre: str
    descripcion: str = ""
    permiso_ids: list[UUID] = field(default_factory=list)


class CrearRolUseCase:
    def __init__(self, rol_repo: RolRepository, permiso_repo: PermisoRepository):
        self._rol_repo = rol_repo
        self._permiso_repo = permiso_repo

    async def ejecutar(self, data: CrearRolInput) -> Rol:
        codigo = _normalizar_codigo(data.codigo)
        if not codigo or " " in codigo:
            raise CodigoRolDuplicado("El código de rol debe ir en minúsculas y sin espacios")

        if await self._rol_repo.obtener_por_codigo(codigo) is not None:
            raise CodigoRolDuplicado(f"Ya existe un rol con código '{codigo}'")

        if data.permiso_ids and not await self._permiso_repo.existen_todos(data.permiso_ids):
            raise PermisoNoEncontrado("Uno o más permisos no existen en el catálogo")

        rol = Rol(id=uuid4(), nombre=data.nombre, descripcion=data.descripcion, codigo=codigo)
        await self._rol_repo.crear(rol)
        if data.permiso_ids:
            await self._rol_repo.asignar_permisos(rol.id, data.permiso_ids)
        return await self._rol_repo.obtener_por_id(rol.id)


# --------------------------------------------------------------------------- #
@dataclass
class EditarRolInput:
    rol_id: UUID
    nombre: str
    descripcion: str


class EditarRolUseCase:
    """Solo cambia nombre/descripción. El código es inmutable."""

    def __init__(self, rol_repo: RolRepository):
        self._rol_repo = rol_repo

    async def ejecutar(self, data: EditarRolInput) -> Rol:
        rol = await self._rol_repo.obtener_por_id(data.rol_id)
        if rol is None:
            raise RolNoEncontrado(f"No existe rol con id {data.rol_id}")
        await self._rol_repo.actualizar_datos(data.rol_id, data.nombre, data.descripcion)
        return await self._rol_repo.obtener_por_id(data.rol_id)


# --------------------------------------------------------------------------- #
class EliminarRolUseCase:
    def __init__(self, rol_repo: RolRepository):
        self._rol_repo = rol_repo

    async def ejecutar(self, rol_id: UUID) -> None:
        rol = await self._rol_repo.obtener_por_id(rol_id)
        if rol is None:
            raise RolNoEncontrado(f"No existe rol con id {rol_id}")
        if rol.codigo == ROL_ADMIN:
            raise RolAdminProtegido("El rol admin no se puede eliminar")
        if await self._rol_repo.tiene_usuarios(rol_id):
            raise UsuarioNoEncontrado("No se puede eliminar un rol con usuarios asignados")
        await self._rol_repo.eliminar(rol_id)


# --------------------------------------------------------------------------- #
@dataclass
class AsignarPermisosInput:
    rol_id: UUID
    permiso_ids: list[UUID]


class AsignarPermisosRolUseCase:
    def __init__(self, rol_repo: RolRepository, permiso_repo: PermisoRepository):
        self._rol_repo = rol_repo
        self._permiso_repo = permiso_repo

    async def ejecutar(self, data: AsignarPermisosInput) -> Rol:
        rol = await self._rol_repo.obtener_por_id(data.rol_id)
        if rol is None:
            raise RolNoEncontrado(f"No existe rol con id {data.rol_id}")
        if not await self._permiso_repo.existen_todos(data.permiso_ids):
            raise PermisoNoEncontrado("Uno o más permisos no existen en el catálogo")
        await self._rol_repo.asignar_permisos(data.rol_id, data.permiso_ids)
        return await self._rol_repo.obtener_por_id(data.rol_id)


# --------------------------------------------------------------------------- #
class QuitarPermisoRolUseCase:
    def __init__(self, rol_repo: RolRepository):
        self._rol_repo = rol_repo

    async def ejecutar(self, rol_id: UUID, permiso_id: UUID) -> Rol:
        rol = await self._rol_repo.obtener_por_id(rol_id)
        if rol is None:
            raise RolNoEncontrado(f"No existe rol con id {rol_id}")
        await self._rol_repo.quitar_permiso(rol_id, permiso_id)
        return await self._rol_repo.obtener_por_id(rol_id)


# --------------------------------------------------------------------------- #
class ListarRolesUseCase:
    def __init__(self, rol_repo: RolRepository):
        self._rol_repo = rol_repo

    async def ejecutar(self, paginacion: PageParams, orden: Sort) -> Page:
        return await self._rol_repo.listar(paginacion, orden)


class ListarPermisosUseCase:
    def __init__(self, permiso_repo: PermisoRepository):
        self._permiso_repo = permiso_repo

    async def ejecutar(self, paginacion: PageParams, orden: Sort) -> Page:
        return await self._permiso_repo.listar(paginacion, orden)
