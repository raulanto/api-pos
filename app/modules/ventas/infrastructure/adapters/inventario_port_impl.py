from uuid import UUID
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.ventas.application.ports.inventario_port import InventarioPort
from app.modules.inventario.application.use_cases.aplicar_movimiento import (
    AplicarMovimientoUseCase, AplicarMovimientoInput,
)
from app.modules.inventario.domain.value_objects import TipoMovimiento
from app.modules.inventario.infrastructure.persistence.repositories import (
    SqlAlchemyProductoRepository,
    SqlAlchemyExistenciaRepository,
    SqlAlchemyMovimientoRepository,
)


class InventarioPortImpl(InventarioPort):
    def __init__(self, db: AsyncSession):
        self._db = db
        # Reutiliza el caso de uso del módulo inventario con la MISMA sesión, de
        # modo que todo cae en la transacción única del request (get_db).
        self._use_case = AplicarMovimientoUseCase(
            producto_repo=SqlAlchemyProductoRepository(db),
            existencia_repo=SqlAlchemyExistenciaRepository(db),
            movimiento_repo=SqlAlchemyMovimientoRepository(db),
        )

    async def descontar_stock(
        self, producto_id: UUID, sucursal_id: UUID, cantidad: Decimal,
        referencia_venta_id: UUID, usuario_id: UUID
    ) -> None:
        await self._use_case.ejecutar(AplicarMovimientoInput(
            producto_id=producto_id,
            sucursal_id=sucursal_id,
            tipo=TipoMovimiento.SALIDA,
            cantidad=cantidad,
            referencia_tipo="venta",
            referencia_id=referencia_venta_id,
            usuario_id=usuario_id,
            motivo=f"Venta {referencia_venta_id}",
        ))

    async def reingresar_stock(
        self, producto_id: UUID, sucursal_id: UUID, cantidad: Decimal,
        referencia_venta_id: UUID, usuario_id: UUID
    ) -> None:
        await self._use_case.ejecutar(AplicarMovimientoInput(
            producto_id=producto_id,
            sucursal_id=sucursal_id,
            tipo=TipoMovimiento.ENTRADA,
            cantidad=cantidad,
            referencia_tipo="anulacion_venta",
            referencia_id=referencia_venta_id,
            usuario_id=usuario_id,
            motivo=f"Anulación de venta {referencia_venta_id}",
        ))
