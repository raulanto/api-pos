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
    SqlAlchemyProductoUnidadRepository,
    SqlAlchemyExistenciaRepository,
    SqlAlchemyMovimientoRepository,
)


class InventarioPortImpl(InventarioPort):
    def __init__(self, db: AsyncSession):
        self._db = db
        self._producto_repo = SqlAlchemyProductoRepository(db)
        self._componente_repo = SqlAlchemyProductoComponenteRepository(db)
        self._unidad_repo = SqlAlchemyProductoUnidadRepository(db)
        # Reutiliza el caso de uso del módulo inventario con la MISMA sesión, de
        # modo que todo cae en la transacción única del request (get_db).
        self._use_case = AplicarMovimientoUseCase(
            producto_repo=self._producto_repo,
            existencia_repo=SqlAlchemyExistenciaRepository(db),
            movimiento_repo=SqlAlchemyMovimientoRepository(db),
        )

    async def _a_unidades_base(
        self, producto_id: UUID, cantidad: Decimal, producto_unidad_id: UUID | None
    ) -> Decimal:
        """Convierte `cantidad` de la presentación a unidades base."""
        if producto_unidad_id is None:
            return cantidad
        unidad = await self._unidad_repo.obtener(producto_unidad_id)
        if unidad is None or unidad.producto_id != producto_id:
            raise ValueError(
                f"La presentación {producto_unidad_id} no corresponde al producto "
                f"{producto_id}."
            )
        # Redondeo a 4 decimales: 6 * (1/6) => 1.0000, no 1.000002.
        return (cantidad * unidad.factor).quantize(Decimal("0.0001"))

    async def _expandir(
        self, producto_id: UUID, cantidad_base: Decimal
    ) -> list[tuple[UUID, Decimal]]:
        """Un kit se explota en sus componentes; un producto simple se devuelve tal cual."""
        producto = await self._producto_repo.obtener_por_id(producto_id)
        if producto is None or producto.tipo != TipoProducto.KIT:
            return [(producto_id, cantidad_base)]
        lineas = await self._componente_repo.listar_por_kit(producto_id)
        return [(l.producto_componente_id, l.cantidad * cantidad_base) for l in lineas]

    async def _aplicar(
        self, tipo: TipoMovimiento, referencia_tipo: str, motivo: str,
        producto_id: UUID, sucursal_id: UUID, cantidad: Decimal,
        referencia_venta_id: UUID, usuario_id: UUID, producto_unidad_id: UUID | None,
    ) -> None:
        cantidad_base = await self._a_unidades_base(
            producto_id, cantidad, producto_unidad_id
        )
        for pid, qty in await self._expandir(producto_id, cantidad_base):
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
        referencia_venta_id: UUID, usuario_id: UUID,
        producto_unidad_id: UUID | None = None,
    ) -> None:
        await self._aplicar(
            TipoMovimiento.SALIDA, "venta", f"Venta {referencia_venta_id}",
            producto_id, sucursal_id, cantidad, referencia_venta_id, usuario_id,
            producto_unidad_id,
        )

    async def reingresar_stock(
        self, producto_id: UUID, sucursal_id: UUID, cantidad: Decimal,
        referencia_venta_id: UUID, usuario_id: UUID,
        producto_unidad_id: UUID | None = None,
    ) -> None:
        await self._aplicar(
            TipoMovimiento.ENTRADA, "anulacion_venta",
            f"Anulación de venta {referencia_venta_id}",
            producto_id, sucursal_id, cantidad, referencia_venta_id, usuario_id,
            producto_unidad_id,
        )
