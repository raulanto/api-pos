from uuid import UUID
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.ventas.application.ports.inventario_port import InventarioPort
from app.modules.inventario.application.use_cases.aplicar_movimiento import (
    AplicarMovimientoUseCase, AplicarMovimientoInput,
)
from app.modules.inventario.domain.value_objects import TipoMovimiento, TipoProducto
from app.modules.inventario.infrastructure.persistence.repositories import (
    SqlAlchemyProductoRepository,
    SqlAlchemyProductoComponenteRepository,
    SqlAlchemyExistenciaRepository,
    SqlAlchemyMovimientoRepository,
)


class InventarioPortImpl(InventarioPort):
    def __init__(self, db: AsyncSession):
        self._db = db
        self._producto_repo = SqlAlchemyProductoRepository(db)
        self._componente_repo = SqlAlchemyProductoComponenteRepository(db)
        # Reutiliza el caso de uso del módulo inventario con la MISMA sesión, de
        # modo que todo cae en la transacción única del request (get_db).
        self._use_case = AplicarMovimientoUseCase(
            producto_repo=self._producto_repo,
            existencia_repo=SqlAlchemyExistenciaRepository(db),
            movimiento_repo=SqlAlchemyMovimientoRepository(db),
        )

    async def _expandir(
        self, producto_id: UUID, cantidad: Decimal
    ) -> list[tuple[UUID, Decimal]]:
        """Un kit se explota en sus componentes (`cantidad_receta * cantidad`);
        un producto simple se devuelve tal cual."""
        producto = await self._producto_repo.obtener_por_id(producto_id)
        if producto is None or producto.tipo != TipoProducto.KIT:
            return [(producto_id, cantidad)]
        lineas = await self._componente_repo.listar_por_kit(producto_id)
        return [(l.producto_componente_id, l.cantidad * cantidad) for l in lineas]

    async def _aplicar(
        self, tipo: TipoMovimiento, referencia_tipo: str, motivo: str,
        producto_id: UUID, sucursal_id: UUID, cantidad: Decimal,
        referencia_venta_id: UUID, usuario_id: UUID,
    ) -> None:
        for pid, qty in await self._expandir(producto_id, cantidad):
            await self._use_case.ejecutar(AplicarMovimientoInput(
                producto_id=pid,
                sucursal_id=sucursal_id,
                tipo=tipo,
                cantidad=qty,
                referencia_tipo=referencia_tipo,
                referencia_id=referencia_venta_id,
                usuario_id=usuario_id,
                motivo=motivo,
            ))

    async def descontar_stock(
        self, producto_id: UUID, sucursal_id: UUID, cantidad: Decimal,
        referencia_venta_id: UUID, usuario_id: UUID
    ) -> None:
        await self._aplicar(
            TipoMovimiento.SALIDA, "venta", f"Venta {referencia_venta_id}",
            producto_id, sucursal_id, cantidad, referencia_venta_id, usuario_id,
        )

    async def reingresar_stock(
        self, producto_id: UUID, sucursal_id: UUID, cantidad: Decimal,
        referencia_venta_id: UUID, usuario_id: UUID
    ) -> None:
        await self._aplicar(
            TipoMovimiento.ENTRADA, "anulacion_venta",
            f"Anulación de venta {referencia_venta_id}",
            producto_id, sucursal_id, cantidad, referencia_venta_id, usuario_id,
        )
