from abc import ABC, abstractmethod
from uuid import UUID
from decimal import Decimal

class InventarioPort(ABC):
    @abstractmethod
    async def descontar_stock(
        self, producto_id: UUID, sucursal_id: UUID, cantidad: Decimal,
        referencia_venta_id: UUID, usuario_id: UUID
    ) -> None: ...
