from uuid import UUID, uuid4
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.ventas.application.ports.inventario_port import InventarioPort
from app.modules.inventario.application.use_cases.aplicar_movimiento import (
    AplicarMovimientoUseCase, AplicarMovimientoInput, DECIMALES_STOCK_DEFAULT,
)
from app.modules.inventario.domain.entities import (
    MovimientoInventario, Existencia, InstanciaAbierta,
)
from app.modules.inventario.domain.value_objects import TipoMovimiento, TipoProducto
from app.modules.inventario.infrastructure.persistence.repositories import (
    SqlAlchemyProductoRepository,
    SqlAlchemyProductoComponenteRepository,
    SqlAlchemyProductoUnidadRepository,
    SqlAlchemyUnidadMedidaRepository,
    SqlAlchemyLoteRepository,
    SqlAlchemyExistenciaRepository,
    SqlAlchemyMovimientoRepository,
    SqlAlchemyInstanciaAbiertaRepository,
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
        self._instancia_repo = SqlAlchemyInstanciaAbiertaRepository(db)
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

    async def _decimales_stock(self, producto, producto_unidad_id: UUID | None) -> int:
        """Decimales para guardar la cantidad en unidad base. Al vender una
        PRESENTACIÓN cuyo `factor < 1` (sub-unidad, ej: 1 botella = 1/8 de reja),
        el resultado en unidad base es fraccional aunque la unidad base sea
        entera: se usa la precisión de la columna (NUMERIC 14,4)."""
        dec = await self._decimales(producto)
        if producto_unidad_id is not None:
            return max(dec, DECIMALES_STOCK_DEFAULT)
        return dec

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
        decimales = await self._decimales_stock(producto, producto_unidad_id)
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
        decimales = await self._decimales_stock(producto, producto_unidad_id)
        cantidad_base = _cuantizar(cantidad * factor, decimales)

        if cantidad_base <= 0:
            raise ValueError(
                f"La venta de {cantidad} de esa presentación equivale a 0 en unidad "
                f"base ({producto.unidad_medida}); revisá el `factor` de la presentación."
            )

        # Las reglas de fraccionamiento ("no admite medio", "múltiplo de X")
        # aplican a la venta EN UNIDAD BASE. Al vender una presentación entera se
        # omiten: el cliente compró N presentaciones discretas, no una fracción.
        if producto_unidad_id is None:
            producto.validar_cantidad_vendible(cantidad_base)

        # Venta a granel = sin presentación (se vendió en unidad base). Sólo en
        # ese caso un producto que rastrea instancias consume de envases abiertos;
        # vender una presentación sellada sigue la ruta normal.
        es_granel = producto_unidad_id is None

        for pid, qty in await self._expandir(producto, cantidad_base):
            # En un kit, cada componente se consume siempre en unidad base
            # (granel) aunque el kit se vendió como presentación.
            comp_granel = es_granel or pid != producto_id
            await self._descontar_una(
                pid, sucursal_id, qty, referencia_venta_id, usuario_id,
                producto_unidad_id=producto_unidad_id if pid == producto_id else None,
                cantidad_capturada=(
                    cantidad if pid == producto_id and producto_unidad_id else None
                ),
                es_granel=comp_granel,
            )

    async def _descontar_una(
        self, pid: UUID, sucursal_id: UUID, qty: Decimal,
        venta_id: UUID, usuario_id: UUID,
        producto_unidad_id: UUID | None, cantidad_capturada: Decimal | None,
        es_granel: bool,
    ) -> None:
        producto = await self._cargar_producto(pid)
        if es_granel and producto.rastrea_instancia_abierta:
            await self._consumir_de_instancias(producto, sucursal_id, qty, venta_id, usuario_id)
            return
        # Ruta normal: productos con control por lote descuentan por FEFO dentro
        # del caso de uso (no se pasa `lote_id`).
        await self._use_case.ejecutar(AplicarMovimientoInput(
            producto_id=pid,
            sucursal_id=sucursal_id,
            tipo=TipoMovimiento.SALIDA,
            cantidad=qty,
            referencia_tipo="venta",
            referencia_id=venta_id,
            usuario_id=usuario_id,
            motivo=f"Venta {venta_id}",
            unidad_capturada_id=producto_unidad_id,
            cantidad_capturada=cantidad_capturada,
        ))

    async def _consumir_de_instancias(
        self, producto, sucursal_id: UUID, qty: Decimal, venta_id: UUID, usuario_id: UUID,
    ) -> None:
        """FIFO sobre las instancias abiertas; auto-abre `instancia_capacidad_default`
        cuando falta saldo. Cada tramo es un SALIDA con su `instancia_abierta_id`."""
        restante = qty
        for inst in await self._instancia_repo.listar_abiertas(producto.id, sucursal_id):
            if restante <= 0:
                break
            toma = inst.saldo if inst.saldo < restante else restante
            await self._mover_instancia(inst, toma, venta_id, usuario_id)
            restante -= toma

        while restante > 0:
            cap = producto.instancia_capacidad_default
            if cap is None or cap <= 0:
                raise ValueError(
                    f"{producto.nombre} rastrea instancias pero no tiene "
                    "`instancia_capacidad_default` para auto-abrir un envase."
                )
            lote_id = await self._lote_fefo_para(producto, sucursal_id, cap)
            inst = InstanciaAbierta.abrir(
                producto_id=producto.id, sucursal_id=sucursal_id,
                capacidad=cap, abierta_por=usuario_id, lote_id=lote_id,
            )
            await self._instancia_repo.crear(inst)
            toma = cap if cap < restante else restante
            await self._mover_instancia(inst, toma, venta_id, usuario_id)
            restante -= toma

    async def _mover_instancia(
        self, inst, toma: Decimal, venta_id: UUID, usuario_id: UUID,
    ) -> None:
        inst.consumir(toma, motivo=f"Venta {venta_id}")
        await self._use_case.ejecutar(AplicarMovimientoInput(
            producto_id=inst.producto_id,
            sucursal_id=inst.sucursal_id,
            tipo=TipoMovimiento.SALIDA,
            cantidad=toma,
            referencia_tipo="venta",
            referencia_id=venta_id,
            usuario_id=usuario_id,
            motivo=f"Venta {venta_id}",
            lote_id=inst.lote_id,
            instancia_abierta_id=inst.id,
        ))
        await self._instancia_repo.actualizar(inst)

    async def _lote_fefo_para(
        self, producto, sucursal_id: UUID, capacidad: Decimal,
    ) -> UUID | None:
        if not producto.requiere_lote:
            return None
        fefo = await self._lote_repo.lotes_fefo(producto.id, sucursal_id)
        for lid, disp in fefo:
            if disp >= capacidad:
                return lid
        return fefo[0][0] if fefo else None

    async def precio_mayoreo_aplicable(
        self, producto_id: UUID, cantidad: Decimal,
    ) -> Decimal | None:
        producto = await self._cargar_producto(producto_id)
        if (
            producto.precio_mayoreo is not None
            and producto.cantidad_minima_mayoreo is not None
            and cantidad >= producto.cantidad_minima_mayoreo
        ):
            return producto.precio_mayoreo
        return None

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

            # Si la salida vino de un envase abierto, devolvé el contenido a esa
            # instancia (la reabre si había quedado agotada).
            if m.instancia_abierta_id is not None:
                inst = await self._instancia_repo.obtener(m.instancia_abierta_id)
                if inst is not None:
                    inst.reponer(m.cantidad)
                    await self._instancia_repo.actualizar(inst)
