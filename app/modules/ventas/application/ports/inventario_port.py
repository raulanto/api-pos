from abc import ABC, abstractmethod
from uuid import UUID
from decimal import Decimal

class InventarioPort(ABC):
    @abstractmethod
    async def descontar_stock(
        self, producto_id: UUID, sucursal_id: UUID, cantidad: Decimal,
        referencia_venta_id: UUID, usuario_id: UUID,
        producto_unidad_id: UUID | None = None,
    ) -> None:
        """Descuenta stock por una venta. Si `producto_unidad_id` viene, la
        cantidad se multiplica por el `factor` de esa presentación; si el
        producto es un kit, se explota su receta."""
        ...

    @abstractmethod
    async def reingresar_stock(
        self, producto_id: UUID, sucursal_id: UUID, cantidad: Decimal,
        referencia_venta_id: UUID, usuario_id: UUID,
        producto_unidad_id: UUID | None = None,
    ) -> None:
        """Devuelve stock al anular una venta (movimiento de ENTRADA), aplicando
        el mismo `factor` / explosión de kit que en la venta original."""
        ...
