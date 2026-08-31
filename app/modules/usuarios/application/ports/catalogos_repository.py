from abc import ABC, abstractmethod
from uuid import UUID
from app.modules.usuarios.domain.entities import Rol, Sucursal

class RolRepository(ABC):
    @abstractmethod
    async def obtener_por_id(self, rol_id: UUID) -> Rol | None: ...

class SucursalRepository(ABC):
    @abstractmethod
    async def obtener_por_id(self, sucursal_id: UUID) -> Sucursal | None: ...
