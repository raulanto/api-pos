from abc import ABC, abstractmethod
from uuid import UUID
from app.modules.inventario.domain.entities import Categoria
from app.modules.inventario.application.dtos import FiltroCategorias
from app.shared.responses import Page, PageParams, Sort


class CategoriaRepository(ABC):
    @abstractmethod
    async def guardar(self, categoria: Categoria) -> None: ...

    @abstractmethod
    async def actualizar(self, categoria: Categoria) -> None: ...

    @abstractmethod
    async def obtener_por_id(
        self, categoria_id: UUID, includes: frozenset[str] = frozenset()
    ) -> Categoria | None: ...

    @abstractmethod
    async def listar(
        self,
        filtro: FiltroCategorias,
        paginacion: PageParams,
        orden: Sort,
        includes: frozenset[str] = frozenset(),
    ) -> Page: ...

    @abstractmethod
    async def tiene_productos_activos(self, categoria_id: UUID) -> bool: ...
