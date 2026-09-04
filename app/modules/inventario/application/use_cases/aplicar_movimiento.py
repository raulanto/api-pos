from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID, uuid4

from app.modules.inventario.domain.entities import MovimientoInventario, Existencia
from app.modules.inventario.domain.value_objects import TipoMovimiento
from app.modules.inventario.domain.exceptions import (
    ProductoNoEncontrado, StockInsuficiente, AjusteSinCantidadFinal, TransferenciaInvalida,
)
from app.modules.inventario.application.ports.producto_repository import ProductoRepository
from app.modules.inventario.application.ports.existencia_repository import ExistenciaRepository
from app.modules.inventario.application.ports.movimiento_repository import MovimientoRepository
from app.modules.inventario.application.ports.event_port import EventPort

EVENTO_MOVIMIENTO = "MovimientoInventarioRegistrado"


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


class AplicarMovimientoUseCase:
    def __init__(
        self,
        producto_repo: ProductoRepository,
        existencia_repo: ExistenciaRepository,
        movimiento_repo: MovimientoRepository,
        event_port: EventPort | None = None,
    ):
        self._producto_repo = producto_repo
        self._existencia_repo = existencia_repo
        self._movimiento_repo = movimiento_repo
        self._event_port = event_port

    async def ejecutar(self, data: AplicarMovimientoInput) -> None:
        if data.tipo == TipoMovimiento.TRANSFERENCIA:
            raise TransferenciaInvalida(
                "Una transferencia se registra en POST /movimientos/transferencia, "
                "no en POST /movimientos."
            )

        producto = await self._producto_repo.obtener_por_id(data.producto_id)
        if not producto:
            raise ProductoNoEncontrado(f"No existe el producto {data.producto_id}")

        existencia = await self._existencia_repo.obtener(data.producto_id, data.sucursal_id)
        cantidad_actual = existencia.cantidad if existencia else Decimal("0")

        if data.tipo == TipoMovimiento.AJUSTE:
            if data.cantidad_final is None:
                raise AjusteSinCantidadFinal(
                    "Un movimiento de AJUSTE requiere `cantidad_final` (el saldo objetivo)."
                )
            nuevo_saldo = data.cantidad_final
            delta = nuevo_saldo - cantidad_actual
            cantidad_movimiento = abs(delta)
        elif data.tipo == TipoMovimiento.ENTRADA:
            cantidad_movimiento = _requerir_cantidad(data.cantidad)
            nuevo_saldo = cantidad_actual + cantidad_movimiento
        elif data.tipo in (TipoMovimiento.SALIDA, TipoMovimiento.MERMA):
            cantidad_movimiento = _requerir_cantidad(data.cantidad)
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
        )
        await self._movimiento_repo.guardar(movimiento)

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

        await self._quiza_actualizar_precios(producto, data)
        await self._publicar_auditoria(data, movimiento, cantidad_actual, nuevo_saldo)

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
        movimiento: MovimientoInventario,
        saldo_anterior: Decimal,
        saldo_nuevo: Decimal,
    ) -> None:
        if self._event_port is None:
            return
        await self._event_port.publicar(EVENTO_MOVIMIENTO, {
            "usuario_id": data.usuario_id,
            "modulo": "inventario",
            "accion": f"movimiento_{data.tipo.value}",
            "entidad": "MovimientoInventario",
            "entidad_id": str(movimiento.id),
            "detalle": {
                "producto_id": str(data.producto_id),
                "sucursal_id": str(data.sucursal_id),
                "tipo": data.tipo.value,
                "cantidad": str(movimiento.cantidad),
                "saldo_anterior": str(saldo_anterior),
                "saldo_nuevo": str(saldo_nuevo),
                "referencia_tipo": data.referencia_tipo,
                "referencia_id": str(data.referencia_id) if data.referencia_id else None,
                "motivo": data.motivo,
                "costo_actualizado": (
                    str(data.costo_unitario) if data.actualizar_costo else None
                ),
                "precio_venta_actualizado": (
                    str(data.nuevo_precio_venta) if data.nuevo_precio_venta is not None else None
                ),
            },
        })


def _requerir_cantidad(cantidad: Decimal | None) -> Decimal:
    if cantidad is None or cantidad <= 0:
        raise ValueError("La cantidad del movimiento debe ser un número positivo.")
    return cantidad
