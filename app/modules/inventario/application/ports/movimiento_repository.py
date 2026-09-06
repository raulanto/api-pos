from abc import ABC, abstractmethod
from uuid import UUID
from app.modules.inventario.domain.entities import MovimientoInventario
from app.modules.inventario.domain.value_objects import TipoMovimiento
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
    async def existe_para_producto(self, producto_id: UUID) -> bool:
        """True si hay al menos un movimiento de inventario de ese producto.
        Se usa para decidir si un producto puede borrarse físicamente."""
        ...

    @abstractmethod
    async def listar_por_referencia(
        self, referencia_id: UUID, tipo: TipoMovimiento | None = None,
        referencia_tipo: str | None = None,
    ) -> list[MovimientoInventario]:
        """Movimientos ligados a una referencia (p. ej. todos los de una venta),
        ordenados por antigüedad. Para revertir el efecto de una venta al anular."""
        ...

    @abstractmethod
    async def listar(
        self,
        filtro: FiltroMovimientos,
        paginacion: PageParams,
        orden: Sort,
        includes: frozenset[str] = frozenset(),
    ) -> Page: ...
