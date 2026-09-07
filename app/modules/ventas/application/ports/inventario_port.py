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
    async def stock_disponible(
        self, producto_id: UUID, sucursal_id: UUID,
        producto_unidad_id: UUID | None = None,
    ) -> Decimal | None:
        """Cantidad disponible expresada en la unidad de la línea (si viene
        `producto_unidad_id`, en esa presentación). `None` = ilimitado a efectos
        de la cotización (servicio, `permite_venta_sin_stock`, kit sin receta).
        Sólo lectura, sin lock: es para previsualizar, no reserva nada."""
        ...

    @abstractmethod
    async def precio_mayoreo_aplicable(
        self, producto_id: UUID, cantidad: Decimal,
    ) -> Decimal | None:
        """`precio_mayoreo` del producto si `cantidad` (en unidad base) alcanza
        `cantidad_minima_mayoreo`; None si va a precio de menudeo o no tiene mayoreo."""
        ...

    @abstractmethod
    async def reponer_parcial(
        self, venta_id: UUID, producto_id: UUID, cantidad_base: Decimal,
        sucursal_id: UUID, devolucion_id: UUID, usuario_id: UUID,
    ) -> None:
        """Devolución parcial: ENTRADA de `cantidad_base` (unidad base) del
        producto, repartida contra las SALIDAS que la venta generó para ese
        producto (mismo `lote_id` de cada tramo, orden de creación). Un kit se
        explota; un servicio no toca stock."""
        ...

    @abstractmethod
    async def revertir_venta(self, venta_id: UUID, usuario_id: UUID) -> None:
        """Anula el efecto en inventario de una venta: por cada movimiento de
        SALIDA que la venta generó, registra la ENTRADA inversa al MISMO lote y
        sucursal, y ajusta el saldo (agregado y por lote). Es exacto para kits,
        presentaciones y salidas FEFO repartidas entre varios lotes."""
        ...
