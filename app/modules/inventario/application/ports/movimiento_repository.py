from abc import ABC, abstractmethod
from uuid import UUID
from app.modules.inventario.domain.entities import MovimientoInventario
from app.modules.inventario.application.dtos import FiltroMovimientos, Paginacion, Pagina

class MovimientoRepository(ABC):
    @abstractmethod
    async def guardar(self, movimiento: MovimientoInventario) -> None: ...

    @abstractmethod
    async def obtener_por_id(self, movimiento_id: UUID) -> MovimientoInventario | None: ...

    @abstractmethod
    async def listar(self, filtro: FiltroMovimientos, paginacion: Paginacion) -> Pagina: ...
