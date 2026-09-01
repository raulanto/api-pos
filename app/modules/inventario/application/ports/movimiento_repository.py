from abc import ABC, abstractmethod
from uuid import UUID
from app.modules.inventario.domain.entities import MovimientoInventario
from app.modules.inventario.application.dtos import FiltroMovimientos
from app.shared.responses import Page, PageParams, Sort

class MovimientoRepository(ABC):
    @abstractmethod
    async def guardar(self, movimiento: MovimientoInventario) -> None: ...

    @abstractmethod
    async def obtener_por_id(
        self, movimiento_id: UUID, includes: frozenset[str] = frozenset()
    ) -> MovimientoInventario | None: ...

    @abstractmethod
    async def listar(
        self,
        filtro: FiltroMovimientos,
        paginacion: PageParams,
        orden: Sort,
        includes: frozenset[str] = frozenset(),
    ) -> Page: ...
