from abc import ABC, abstractmethod
from uuid import UUID
from app.modules.ventas.domain.entities import Venta

class VentaRepository(ABC):
    @abstractmethod
    async def guardar(self, venta: Venta) -> None: ...

    @abstractmethod
    async def obtener_por_id(self, venta_id: UUID) -> Venta | None: ...
