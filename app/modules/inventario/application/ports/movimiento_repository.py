from abc import ABC, abstractmethod
from app.modules.inventario.domain.entities import MovimientoInventario

class MovimientoRepository(ABC):
    @abstractmethod
    async def guardar(self, movimiento: MovimientoInventario) -> None: ...
