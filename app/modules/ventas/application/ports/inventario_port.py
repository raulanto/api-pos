from abc import ABC, abstractmethod
from uuid import UUID
from decimal import Decimal

class InventarioPort(ABC):
    @abstractmethod
    async def descontar_stock(
        self, producto_id: UUID, sucursal_id: UUID, cantidad: Decimal,
        referencia_venta_id: UUID, usuario_id: UUID
    ) -> None: ...

    @abstractmethod
    async def reingresar_stock(
        self, producto_id: UUID, sucursal_id: UUID, cantidad: Decimal,
        referencia_venta_id: UUID, usuario_id: UUID
    ) -> None:
        """Devuelve stock al anular una venta (movimiento de ENTRADA)."""
        ...
