from abc import ABC, abstractmethod
from uuid import UUID

from app.modules.sucursales.domain.entities import Sucursal
from app.modules.sucursales.application.dtos import FiltroSucursales
from app.shared.responses import Page, PageParams, Sort


class SucursalRepository(ABC):
    @abstractmethod
    async def obtener_por_id(self, sucursal_id: UUID) -> Sucursal | None: ...

    @abstractmethod
    async def obtener_por_nombre(self, nombre: str) -> Sucursal | None: ...

    @abstractmethod
    async def obtener_por_codigo(self, codigo: str) -> Sucursal | None: ...

    @abstractmethod
    async def listar(
        self, filtro: FiltroSucursales, paginacion: PageParams, orden: Sort
    ) -> Page: ...

    @abstractmethod
    async def crear(self, sucursal: Sucursal) -> Sucursal: ...

    @abstractmethod
    async def actualizar(self, sucursal: Sucursal) -> None: ...

    @abstractmethod
    async def tiene_usuarios_activos(self, sucursal_id: UUID) -> bool:
        """True si hay usuarios activos asignados a la sucursal. Lee la tabla
        `usuario` (columna `sucursal_id`) — es una lectura cross-tabla, no una
        dependencia de código del módulo usuarios."""
        ...
