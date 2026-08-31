from abc import ABC, abstractmethod
from uuid import UUID
from app.modules.usuarios.domain.entities import Rol, Sucursal, Permiso


class RolRepository(ABC):
    @abstractmethod
    async def obtener_por_id(self, rol_id: UUID) -> Rol | None: ...

    @abstractmethod
    async def obtener_por_codigo(self, codigo: str) -> Rol | None: ...

    @abstractmethod
    async def listar(self) -> list[Rol]: ...

    @abstractmethod
    async def crear(self, rol: Rol) -> Rol: ...

    @abstractmethod
    async def actualizar_datos(self, rol_id: UUID, nombre: str, descripcion: str) -> None: ...

    @abstractmethod
    async def eliminar(self, rol_id: UUID) -> None: ...

    @abstractmethod
    async def tiene_usuarios(self, rol_id: UUID) -> bool: ...

    @abstractmethod
    async def asignar_permisos(self, rol_id: UUID, permiso_ids: list[UUID]) -> None: ...

    @abstractmethod
    async def quitar_permiso(self, rol_id: UUID, permiso_id: UUID) -> None: ...


class PermisoRepository(ABC):
    @abstractmethod
    async def listar(self) -> list[Permiso]: ...

    @abstractmethod
    async def obtener_por_id(self, permiso_id: UUID) -> Permiso | None: ...

    @abstractmethod
    async def existen_todos(self, permiso_ids: list[UUID]) -> bool: ...


class SucursalRepository(ABC):
    @abstractmethod
    async def obtener_por_id(self, sucursal_id: UUID) -> Sucursal | None: ...
