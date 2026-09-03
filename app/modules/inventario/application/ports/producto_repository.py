from abc import ABC, abstractmethod
from uuid import UUID
from app.modules.inventario.domain.entities import Producto
from app.modules.inventario.application.dtos import FiltroProductos, ProductoKpis
from app.shared.responses import Page, PageParams, Sort

class ProductoRepository(ABC):
    @abstractmethod
    async def guardar(self, producto: Producto) -> None: ...

    @abstractmethod
    async def actualizar(self, producto: Producto) -> None: ...

    @abstractmethod
    async def obtener_por_id(
        self, producto_id: UUID, includes: frozenset[str] = frozenset()
    ) -> Producto | None: ...

    @abstractmethod
    async def buscar_por_sku(self, sku: str, solo_activos: bool = True) -> Producto | None: ...

    @abstractmethod
    async def buscar_por_codigo_barras(
        self, codigo_barras: str, solo_activos: bool = True
    ) -> Producto | None: ...

    @abstractmethod
    async def listar(
        self,
        filtro: FiltroProductos,
        paginacion: PageParams,
        orden: Sort,
        includes: frozenset[str] = frozenset(),
    ) -> Page: ...

    @abstractmethod
    async def kpis(self, filtro: FiltroProductos) -> ProductoKpis: ...
