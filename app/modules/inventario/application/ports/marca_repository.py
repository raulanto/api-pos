from abc import ABC, abstractmethod
from uuid import UUID
from app.modules.inventario.domain.entities import Marca
from app.modules.inventario.application.dtos import FiltroMarcas
from app.shared.responses import Page, PageParams, Sort


class MarcaRepository(ABC):
    @abstractmethod
    async def guardar(self, marca: Marca) -> None: ...

    @abstractmethod
    async def actualizar(self, marca: Marca) -> None: ...

    @abstractmethod
    async def obtener_por_id(self, marca_id: UUID) -> Marca | None: ...

    @abstractmethod
    async def listar(
        self,
        filtro: FiltroMarcas,
        paginacion: PageParams,
        orden: Sort,
    ) -> Page: ...

    @abstractmethod
    async def tiene_productos_activos(self, marca_id: UUID) -> bool: ...

    @abstractmethod
    async def eliminar(self, marca_id: UUID) -> None: ...

