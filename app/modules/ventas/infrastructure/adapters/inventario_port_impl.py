from uuid import UUID, uuid4
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.ventas.application.ports.inventario_port import InventarioPort
from app.modules.inventario.application.use_cases.aplicar_movimiento import (
    AplicarMovimientoUseCase, AplicarMovimientoInput, DECIMALES_STOCK_DEFAULT,
)
from app.modules.inventario.domain.entities import MovimientoInventario, Existencia
from app.modules.inventario.domain.value_objects import TipoMovimiento, TipoProducto
from app.modules.inventario.infrastructure.persistence.repositories import (
    SqlAlchemyProductoRepository,
    SqlAlchemyProductoComponenteRepository,
    SqlAlchemyProductoUnidadRepository,
    SqlAlchemyUnidadMedidaRepository,
    SqlAlchemyLoteRepository,
    SqlAlchemyExistenciaRepository,
    SqlAlchemyMovimientoRepository,
)


def _cuantizar(valor: Decimal, decimales: int) -> Decimal:
    return valor.quantize(Decimal(1).scaleb(-decimales))


class InventarioPortImpl(InventarioPort):
    def __init__(self, db: AsyncSession):
        self._db = db
        self._producto_repo = SqlAlchemyProductoRepository(db)
        self._componente_repo = SqlAlchemyProductoComponenteRepository(db)
        self._unidad_repo = SqlAlchemyProductoUnidadRepository(db)
        self._um_repo = SqlAlchemyUnidadMedidaRepository(db)
        self._lote_repo = SqlAlchemyLoteRepository(db)
        self._existencia_repo = SqlAlchemyExistenciaRepository(db)
        self._movimiento_repo = SqlAlchemyMovimientoRepository(db)
        # Reutiliza el caso de uso del módulo inventario con la MISMA sesión, de
        # modo que todo cae en la transacción única del request (get_db).
        self._use_case = AplicarMovimientoUseCase(
            producto_repo=self._producto_repo,
            existencia_repo=self._existencia_repo,
            movimiento_repo=self._movimiento_repo,
            unidad_medida_repo=self._um_repo,
            lote_repo=self._lote_repo,
        )

    async def _cargar_producto(self, producto_id: UUID):
        producto = await self._producto_repo.obtener_por_id(producto_id)
        if producto is None:
            raise ValueError(f"No existe el producto {producto_id}.")
        return producto

    async def _decimales(self, producto) -> int:
        if producto.unidad_medida_id is None:
            return DECIMALES_STOCK_DEFAULT
        unidad = await self._um_repo.obtener(producto.unidad_medida_id)
        return unidad.decimales if unidad is not None else DECIMALES_STOCK_DEFAULT

    async def _factor(self, producto_id: UUID, producto_unidad_id: UUID | None) -> Decimal:
        if producto_unidad_id is None:
            return Decimal("1")
        unidad = await self._unidad_repo.obtener(producto_unidad_id)
        if unidad is None or unidad.producto_id != producto_id:
            raise ValueError(
                f"La presentación {producto_unidad_id} no corresponde al producto "
                f"{producto_id}."
            )
        return unidad.factor

    async def convertir_a_base(
        self, producto_id: UUID, cantidad: Decimal,
        producto_unidad_id: UUID | None = None,
    ) -> Decimal:
        producto = await self._cargar_producto(producto_id)
        factor = await self._factor(producto_id, producto_unidad_id)
        decimales = await self._decimales(producto)
        return _cuantizar(cantidad * factor, decimales)

    async def _expandir(
        self, producto, cantidad_base: Decimal
    ) -> list[tuple[UUID, Decimal]]:
        """Un kit se explota en sus componentes; un producto normal se devuelve tal cual."""
        if producto.tipo != TipoProducto.KIT:
            return [(producto.id, cantidad_base)]
        lineas = await self._componente_repo.listar_por_kit(producto.id)
        return [(l.producto_componente_id, l.cantidad * cantidad_base) for l in lineas]

    async def descontar_stock(
        self, producto_id: UUID, sucursal_id: UUID, cantidad: Decimal,
        referencia_venta_id: UUID, usuario_id: UUID,
        producto_unidad_id: UUID | None = None,
    ) -> None:
        producto = await self._cargar_producto(producto_id)
        if not producto.tipo.mueve_stock:  # SERVICIO: no toca inventario
            return

        factor = await self._factor(producto_id, producto_unidad_id)
        decimales = await self._decimales(producto)
        cantidad_base = _cuantizar(cantidad * factor, decimales)

        # Reglas de fraccionamiento del producto padre sobre la cantidad base.
        producto.validar_cantidad_vendible(cantidad_base)

        for pid, qty in await self._expandir(producto, cantidad_base):
            # Los productos con control por lote descuentan por FEFO dentro del
            # caso de uso (no se pasa `lote_id`).
            await self._use_case.ejecutar(AplicarMovimientoInput(
                producto_id=pid,
                sucursal_id=sucursal_id,
                tipo=TipoMovimiento.SALIDA,
                cantidad=qty,
                referencia_tipo="venta",
                referencia_id=referencia_venta_id,
                usuario_id=usuario_id,
                motivo=f"Venta {referencia_venta_id}",
                unidad_capturada_id=producto_unidad_id,
                cantidad_capturada=cantidad if producto_unidad_id is not None else None,
            ))

    async def revertir_venta(self, venta_id: UUID, usuario_id: UUID) -> None:
        """ENTRADA inversa por cada SALIDA que generó la venta, al mismo lote."""
        salidas = await self._movimiento_repo.listar_por_referencia(
            venta_id, tipo=TipoMovimiento.SALIDA, referencia_tipo="venta",
        )
        for m in salidas:
            reverso = MovimientoInventario.crear(
                producto_id=m.producto_id,
                sucursal_id=m.sucursal_id,
                tipo=TipoMovimiento.ENTRADA,
                cantidad=m.cantidad,
                referencia_tipo="anulacion_venta",
                usuario_id=usuario_id,
                referencia_id=venta_id,
                costo_unitario=m.costo_unitario,
                motivo=f"Anulación de venta {venta_id}",
                lote_id=m.lote_id,
            )
            await self._movimiento_repo.guardar(reverso)

            existencia = await self._existencia_repo.obtener(m.producto_id, m.sucursal_id)
            actual = existencia.cantidad if existencia else Decimal("0")
            nuevo = actual + m.cantidad
            if existencia:
                await self._existencia_repo.actualizar_cantidad(
                    m.producto_id, m.sucursal_id, nuevo
                )
            else:
                await self._existencia_repo.crear(Existencia(
                    id=uuid4(),
                    producto_id=m.producto_id,
                    sucursal_id=m.sucursal_id,
                    cantidad=nuevo,
                    stock_minimo=Decimal("0"),
                    stock_maximo=None,
                ))

            if m.lote_id is not None:
                await self._lote_repo.ajustar_saldo(
                    m.producto_id, m.sucursal_id, m.lote_id, m.cantidad
                )
