from abc import ABC, abstractmethod
from uuid import UUID

from app.modules.proveedores.domain.entities import Proveedor
from app.modules.proveedores.application.dtos import FiltroProveedores
from app.shared.responses import Page, PageParams, Sort


class ProveedorRepository(ABC):
    @abstractmethod
    async def obtener_por_id(self, proveedor_id: UUID) -> Proveedor | None: ...

    @abstractmethod
    async def buscar_por_codigo(self, codigo: str, solo_activos: bool = True) -> Proveedor | None: ...

    @abstractmethod
    async def guardar(self, proveedor: Proveedor) -> None: ...

    @abstractmethod
    async def actualizar(self, proveedor: Proveedor) -> None: ...

    @abstractmethod
    async def listar(
        self, filtro: FiltroProveedores, paginacion: PageParams, orden: Sort,
    ) -> Page: ...
