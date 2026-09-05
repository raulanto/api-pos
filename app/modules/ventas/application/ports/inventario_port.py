from abc import ABC, abstractmethod
from uuid import UUID
from decimal import Decimal

class InventarioPort(ABC):
    @abstractmethod
    async def convertir_a_base(
        self, producto_id: UUID, cantidad: Decimal,
        producto_unidad_id: UUID | None = None,
    ) -> Decimal:
        """Convierte `cantidad` de la presentación indicada a unidades base del
        producto (cantidad * factor), redondeada a los decimales de su unidad de
        medida. Sin `producto_unidad_id` devuelve `cantidad` tal cual."""
        ...

    @abstractmethod
    async def descontar_stock(
        self, producto_id: UUID, sucursal_id: UUID, cantidad: Decimal,
        referencia_venta_id: UUID, usuario_id: UUID,
        producto_unidad_id: UUID | None = None,
    ) -> None:
        """Descuenta stock por una venta. Si `producto_unidad_id` viene, la
        cantidad se multiplica por el `factor` de esa presentación; si el
        producto es un kit, se explota su receta. Un producto de tipo SERVICIO
        no mueve inventario."""
        ...

    @abstractmethod
    async def revertir_venta(self, venta_id: UUID, usuario_id: UUID) -> None:
        """Anula el efecto en inventario de una venta: por cada movimiento de
        SALIDA que la venta generó, registra la ENTRADA inversa al MISMO lote y
        sucursal, y ajusta el saldo (agregado y por lote). Es exacto para kits,
        presentaciones y salidas FEFO repartidas entre varios lotes."""
        ...
