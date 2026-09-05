from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

from app.modules.inventario.domain.entities import MovimientoInventario, Existencia, Lote
from app.modules.inventario.domain.value_objects import TipoMovimiento
from app.modules.inventario.domain.exceptions import (
    ProductoNoEncontrado, StockInsuficiente, AjusteSinCantidadFinal, TransferenciaInvalida,
    LoteRequerido, LoteInvalido,
)
from app.modules.inventario.application.ports.producto_repository import ProductoRepository
from app.modules.inventario.application.ports.existencia_repository import ExistenciaRepository
from app.modules.inventario.application.ports.movimiento_repository import MovimientoRepository
from app.modules.inventario.application.ports.event_port import EventPort
from app.modules.inventario.application.ports.unidad_medida_repository import (
    UnidadMedidaRepository,
)
from app.modules.inventario.application.ports.lote_repository import LoteRepository

EVENTO_MOVIMIENTO = "MovimientoInventarioRegistrado"

# Decimales de la cantidad de stock cuando el producto no tiene unidad de
# catálogo asignada (fallback del texto libre `producto.unidad_medida`).
DECIMALES_STOCK_DEFAULT = 4


def _cuantizar(valor: Decimal, decimales: int) -> Decimal:
    q = Decimal(1).scaleb(-decimales)  # 0 -> 1, 2 -> 0.01, 4 -> 0.0001
    return valor.quantize(q)


@dataclass
class LoteNuevoData:
    """Datos para crear un lote al vuelo en una ENTRADA."""
    codigo_lote: str
    fecha_caducidad: date | None = None
    costo: Decimal | None = None
    proveedor: str | None = None


@dataclass
class AplicarMovimientoInput:
    producto_id: UUID
    sucursal_id: UUID
    tipo: TipoMovimiento
    referencia_tipo: str
    usuario_id: UUID
    cantidad: Decimal | None = None          # requerido salvo AJUSTE
    cantidad_final: Decimal | None = None     # sólo AJUSTE: saldo objetivo absoluto
    referencia_id: UUID | None = None
    costo_unitario: Decimal | None = None
    motivo: str | None = None
    # Sólo se usan al crear la existencia por primera vez.
    stock_minimo: Decimal | None = None
    stock_maximo: Decimal | None = None
    # Precios volátiles: un movimiento puede "empujar" costo/precio al producto.
    actualizar_costo: bool = False            # ENTRADA: producto.costo = costo_unitario
    nuevo_precio_venta: Decimal | None = None  # cualquier tipo: fija producto.precio_venta
    # Trazabilidad: unidad/cantidad tal como se capturaron (antes de convertir a
    # unidad base). `cantidad` ya viene en unidad base.
    unidad_capturada_id: UUID | None = None
    cantidad_capturada: Decimal | None = None
    # Control por lote (sólo productos con `requiere_lote`):
    #   ENTRADA  -> `lote_id` (existente) o `lote_nuevo` (crear al vuelo).
    #   SALIDA/MERMA -> `lote_id` para forzar un lote; si no, FEFO automático.
    #   AJUSTE   -> `lote_id` obligatorio (el objetivo es el saldo de ese lote).
    lote_id: UUID | None = None
    lote_nuevo: LoteNuevoData | None = None


class AplicarMovimientoUseCase:
    def __init__(
        self,
        producto_repo: ProductoRepository,
        existencia_repo: ExistenciaRepository,
        movimiento_repo: MovimientoRepository,
        event_port: EventPort | None = None,
        unidad_medida_repo: UnidadMedidaRepository | None = None,
        lote_repo: LoteRepository | None = None,
    ):
        self._producto_repo = producto_repo
        self._existencia_repo = existencia_repo
        self._movimiento_repo = movimiento_repo
        self._event_port = event_port
        self._unidad_medida_repo = unidad_medida_repo
        self._lote_repo = lote_repo

    async def _decimales_stock(self, producto) -> int:
        """Decimales admitidos por la unidad base del producto (0 para piezas)."""
        if producto.unidad_medida_id is None or self._unidad_medida_repo is None:
            return DECIMALES_STOCK_DEFAULT
        unidad = await self._unidad_medida_repo.obtener(producto.unidad_medida_id)
        return unidad.decimales if unidad is not None else DECIMALES_STOCK_DEFAULT

    async def ejecutar(self, data: AplicarMovimientoInput) -> None:
        if data.tipo == TipoMovimiento.TRANSFERENCIA:
            raise TransferenciaInvalida(
                "Una transferencia se registra en POST /movimientos/transferencia, "
                "no en POST /movimientos."
            )

        producto = await self._producto_repo.obtener_por_id(data.producto_id)
        if not producto:
            raise ProductoNoEncontrado(f"No existe el producto {data.producto_id}")

        decimales = await self._decimales_stock(producto)

        if producto.requiere_lote:
            await self._ejecutar_con_lote(data, producto, decimales)
            return

        await self._ejecutar_sin_lote(data, producto, decimales)

    # ------------------------------------------------------------------ sin lote
    async def _ejecutar_sin_lote(self, data, producto, decimales: int) -> None:
        existencia = await self._existencia_repo.obtener(data.producto_id, data.sucursal_id)
        cantidad_actual = existencia.cantidad if existencia else Decimal("0")

        if data.tipo == TipoMovimiento.AJUSTE:
            if data.cantidad_final is None:
                raise AjusteSinCantidadFinal(
                    "Un movimiento de AJUSTE requiere `cantidad_final` (el saldo objetivo)."
                )
            nuevo_saldo = _cuantizar(data.cantidad_final, decimales)
            cantidad_movimiento = abs(nuevo_saldo - cantidad_actual)
        elif data.tipo == TipoMovimiento.ENTRADA:
            cantidad_movimiento = _cuantizar(_requerir_cantidad(data.cantidad), decimales)
            nuevo_saldo = cantidad_actual + cantidad_movimiento
        elif data.tipo in (TipoMovimiento.SALIDA, TipoMovimiento.MERMA):
            cantidad_cruda = _requerir_cantidad(data.cantidad)
            producto.validar_cantidad_vendible(cantidad_cruda)
            cantidad_movimiento = _cuantizar(cantidad_cruda, decimales)
            nuevo_saldo = cantidad_actual - cantidad_movimiento
            if nuevo_saldo < 0 and not producto.permite_stock_negativo:
                raise StockInsuficiente(
                    f"Stock insuficiente para {producto.nombre}: "
                    f"disponible {cantidad_actual}, solicitado {cantidad_movimiento}"
                )
        else:  # pragma: no cover - enum cerrado
            raise ValueError(f"Tipo de movimiento no soportado: {data.tipo}")

        movimiento = MovimientoInventario.crear(
            producto_id=data.producto_id,
            sucursal_id=data.sucursal_id,
            tipo=data.tipo,
            cantidad=cantidad_movimiento,
            referencia_tipo=data.referencia_tipo,
            usuario_id=data.usuario_id,
            referencia_id=data.referencia_id,
            costo_unitario=data.costo_unitario,
            motivo=data.motivo,
            unidad_capturada_id=data.unidad_capturada_id,
            cantidad_capturada=data.cantidad_capturada,
        )
        await self._movimiento_repo.guardar(movimiento)
        await self._persistir_agregado(data, existencia, nuevo_saldo)
        await self._quiza_actualizar_precios(producto, data)
        await self._publicar_auditoria(
            data, movimiento.id, cantidad_movimiento, cantidad_actual, nuevo_saldo,
        )

    # ------------------------------------------------------------------ con lote
    async def _ejecutar_con_lote(self, data, producto, decimales: int) -> None:
        if self._lote_repo is None:
            raise ValueError(
                "Falta el repositorio de lotes para operar un producto con control por lote."
            )
        existencia = await self._existencia_repo.obtener(data.producto_id, data.sucursal_id)
        cantidad_actual = existencia.cantidad if existencia else Decimal("0")

        if data.tipo == TipoMovimiento.ENTRADA:
            cant = _cuantizar(_requerir_cantidad(data.cantidad), decimales)
            lote = await self._resolver_lote_entrada(data, producto)
            await self._lote_repo.ajustar_saldo(
                data.producto_id, data.sucursal_id, lote.id, cant
            )
            costo = data.costo_unitario if data.costo_unitario is not None else lote.costo
            mov_id = await self._registrar_mov_lote(
                data, data.tipo, cant, lote.id, costo,
            )
            nuevo_saldo = cantidad_actual + cant
            await self._persistir_agregado(data, existencia, nuevo_saldo)
            await self._quiza_actualizar_precios(producto, data)
            await self._publicar_auditoria(
                data, mov_id, cant, cantidad_actual, nuevo_saldo,
                lotes=[{"lote_id": str(lote.id), "cantidad": str(cant)}],
            )
            return

        if data.tipo in (TipoMovimiento.SALIDA, TipoMovimiento.MERMA):
            cruda = _requerir_cantidad(data.cantidad)
            producto.validar_cantidad_vendible(cruda)
            total = _cuantizar(cruda, decimales)
            plan = await self._plan_salida_lote(data, producto, total)
            primer_mov: UUID | None = None
            resumen = []
            for lote_id, qty in plan:
                await self._lote_repo.ajustar_saldo(
                    data.producto_id, data.sucursal_id, lote_id, -qty
                )
                lote = await self._lote_repo.obtener(lote_id)
                mov_id = await self._registrar_mov_lote(
                    data, data.tipo, qty, lote_id,
                    lote.costo if lote is not None else data.costo_unitario,
                )
                primer_mov = primer_mov or mov_id
                resumen.append({"lote_id": str(lote_id), "cantidad": str(qty)})
            nuevo_saldo = cantidad_actual - total
            await self._persistir_agregado(data, existencia, nuevo_saldo)
            await self._quiza_actualizar_precios(producto, data)
            await self._publicar_auditoria(
                data, primer_mov, total, cantidad_actual, nuevo_saldo, lotes=resumen,
            )
            return

        if data.tipo == TipoMovimiento.AJUSTE:
            if data.cantidad_final is None:
                raise AjusteSinCantidadFinal(
                    "Un movimiento de AJUSTE requiere `cantidad_final` (el saldo objetivo)."
                )
            if data.lote_id is None:
                raise LoteRequerido(
                    "Un AJUSTE de un producto con control por lote requiere `lote_id` "
                    "(el objetivo es el saldo de ese lote en la sucursal)."
                )
            lote = await self._lote_repo.obtener(data.lote_id)
            if lote is None or lote.producto_id != data.producto_id:
                raise LoteInvalido(
                    f"El lote {data.lote_id} no pertenece al producto {data.producto_id}."
                )
            saldo_lote = await self._lote_repo.saldo(data.sucursal_id, data.lote_id)
            objetivo = _cuantizar(data.cantidad_final, decimales)
            delta = objetivo - saldo_lote
            await self._lote_repo.ajustar_saldo(
                data.producto_id, data.sucursal_id, data.lote_id, delta
            )
            mov_id = await self._registrar_mov_lote(
                data, data.tipo, abs(delta), data.lote_id, lote.costo,
            )
            nuevo_saldo = cantidad_actual + delta
            await self._persistir_agregado(data, existencia, nuevo_saldo)
            await self._quiza_actualizar_precios(producto, data)
            await self._publicar_auditoria(
                data, mov_id, abs(delta), cantidad_actual, nuevo_saldo,
                lotes=[{"lote_id": str(data.lote_id), "cantidad": str(delta)}],
            )
            return

        raise ValueError(f"Tipo de movimiento no soportado: {data.tipo}")  # pragma: no cover

    async def _resolver_lote_entrada(self, data, producto) -> Lote:
        if data.lote_id is not None:
            lote = await self._lote_repo.obtener(data.lote_id)
            if lote is None or lote.producto_id != producto.id:
                raise LoteInvalido(
                    f"El lote {data.lote_id} no pertenece al producto {producto.id}."
                )
            if not lote.activo:
                raise LoteInvalido(f"El lote {data.lote_id} está inactivo.")
            return lote
        if data.lote_nuevo is not None:
            n = data.lote_nuevo
            existente = await self._lote_repo.obtener_por_codigo(producto.id, n.codigo_lote)
            if existente is not None:
                return existente  # idempotente: mismo código => mismo lote
            costo = n.costo
            if costo is None:
                costo = data.costo_unitario if data.costo_unitario is not None else producto.costo
            lote = Lote.crear(
                producto_id=producto.id,
                codigo_lote=n.codigo_lote,
                costo=costo,
                fecha_caducidad=n.fecha_caducidad,
                proveedor=n.proveedor,
            )
            await self._lote_repo.crear(lote)
            return lote
        raise LoteRequerido(
            f"{producto.nombre} lleva control por lote: indicá `lote_id` o `lote_nuevo` "
            "en la ENTRADA."
        )

    async def _plan_salida_lote(
        self, data, producto, total: Decimal
    ) -> list[tuple[UUID, Decimal]]:
        if data.lote_id is not None:  # lote forzado (override del FEFO)
            lote = await self._lote_repo.obtener(data.lote_id)
            if lote is None or lote.producto_id != data.producto_id:
                raise LoteInvalido(
                    f"El lote {data.lote_id} no pertenece al producto {data.producto_id}."
                )
            disp = await self._lote_repo.saldo(data.sucursal_id, data.lote_id)
            if disp < total and not producto.permite_stock_negativo:
                raise StockInsuficiente(
                    f"Stock insuficiente en el lote {lote.codigo_lote} para "
                    f"{producto.nombre}: disponible {disp}, solicitado {total}"
                )
            return [(data.lote_id, total)]

        disponibles = await self._lote_repo.lotes_fefo(producto.id, data.sucursal_id)
        plan: list[tuple[UUID, Decimal]] = []
        restante = total
        for lote_id, disp in disponibles:
            if restante <= 0:
                break
            toma = disp if disp < restante else restante
            plan.append((lote_id, toma))
            restante -= toma
        if restante > 0:
            if not producto.permite_stock_negativo or not plan:
                raise StockInsuficiente(
                    f"Stock insuficiente para {producto.nombre}: faltan {restante} "
                    "(sin lote disponible para cubrirlo)"
                )
            # Permite negativo: el sobrante lo absorbe el lote FEFO más antiguo.
            lote_id, qty = plan[0]
            plan[0] = (lote_id, qty + restante)
        return plan

    async def _registrar_mov_lote(
        self, data, tipo: TipoMovimiento, cantidad: Decimal, lote_id: UUID,
        costo_unitario: Decimal | None,
    ) -> UUID:
        movimiento = MovimientoInventario.crear(
            producto_id=data.producto_id,
            sucursal_id=data.sucursal_id,
            tipo=tipo,
            cantidad=cantidad,
            referencia_tipo=data.referencia_tipo,
            usuario_id=data.usuario_id,
            referencia_id=data.referencia_id,
            costo_unitario=costo_unitario,
            motivo=data.motivo,
            unidad_capturada_id=data.unidad_capturada_id,
            cantidad_capturada=data.cantidad_capturada,
            lote_id=lote_id,
        )
        await self._movimiento_repo.guardar(movimiento)
        return movimiento.id

    # ------------------------------------------------------------------ comunes
    async def _persistir_agregado(self, data, existencia, nuevo_saldo: Decimal) -> None:
        if not existencia:
            await self._existencia_repo.crear(Existencia(
                id=uuid4(),
                producto_id=data.producto_id,
                sucursal_id=data.sucursal_id,
                cantidad=nuevo_saldo,
                stock_minimo=data.stock_minimo if data.stock_minimo is not None else Decimal("0"),
                stock_maximo=data.stock_maximo,
            ))
        else:
            await self._existencia_repo.actualizar_cantidad(
                data.producto_id, data.sucursal_id, nuevo_saldo
            )

    async def _quiza_actualizar_precios(self, producto, data: AplicarMovimientoInput) -> None:
        """Precios volátiles: el movimiento puede empujar costo/precio al producto."""
        cambio = False
        if data.actualizar_costo:
            if data.costo_unitario is None:
                raise ValueError("`actualizar_costo` requiere `costo_unitario`.")
            if data.tipo != TipoMovimiento.ENTRADA:
                raise ValueError("Sólo un movimiento de ENTRADA puede actualizar el costo.")
            producto.actualizar(costo=data.costo_unitario)
            cambio = True
        if data.nuevo_precio_venta is not None:
            if data.nuevo_precio_venta < 0:
                raise ValueError("`nuevo_precio_venta` no puede ser negativo.")
            producto.actualizar(precio_venta=data.nuevo_precio_venta)
            cambio = True
        if cambio:
            await self._producto_repo.actualizar(producto)

    async def _publicar_auditoria(
        self,
        data: AplicarMovimientoInput,
        movimiento_id: UUID | None,
        cantidad_mov: Decimal,
        saldo_anterior: Decimal,
        saldo_nuevo: Decimal,
        lotes: list[dict] | None = None,
    ) -> None:
        if self._event_port is None:
            return
        detalle = {
            "producto_id": str(data.producto_id),
            "sucursal_id": str(data.sucursal_id),
            "tipo": data.tipo.value,
            "cantidad": str(cantidad_mov),
            "saldo_anterior": str(saldo_anterior),
            "saldo_nuevo": str(saldo_nuevo),
            "referencia_tipo": data.referencia_tipo,
            "referencia_id": str(data.referencia_id) if data.referencia_id else None,
            "motivo": data.motivo,
            "unidad_capturada_id": (
                str(data.unidad_capturada_id) if data.unidad_capturada_id else None
            ),
            "cantidad_capturada": (
                str(data.cantidad_capturada) if data.cantidad_capturada is not None else None
            ),
            "costo_actualizado": str(data.costo_unitario) if data.actualizar_costo else None,
            "precio_venta_actualizado": (
                str(data.nuevo_precio_venta) if data.nuevo_precio_venta is not None else None
            ),
            "lotes": lotes,
        }
        await self._event_port.publicar(EVENTO_MOVIMIENTO, {
            "usuario_id": data.usuario_id,
            "modulo": "inventario",
            "accion": f"movimiento_{data.tipo.value}",
            "entidad": "MovimientoInventario",
            "entidad_id": str(movimiento_id) if movimiento_id else None,
            "detalle": detalle,
        })


def _requerir_cantidad(cantidad: Decimal | None) -> Decimal:
    if cantidad is None or cantidad <= 0:
        raise ValueError("La cantidad del movimiento debe ser un número positivo.")
    return cantidad
