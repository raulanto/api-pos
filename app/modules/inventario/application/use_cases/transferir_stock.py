from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID, uuid4

from app.modules.inventario.domain.entities import MovimientoInventario, Existencia
from app.modules.inventario.domain.value_objects import TipoMovimiento
from app.modules.inventario.domain.exceptions import (
    ProductoNoEncontrado, StockInsuficiente, TransferenciaInvalida,
)
from app.modules.inventario.application.ports.producto_repository import ProductoRepository
from app.modules.inventario.application.ports.existencia_repository import ExistenciaRepository
from app.modules.inventario.application.ports.movimiento_repository import MovimientoRepository
from app.modules.inventario.application.ports.event_port import EventPort

EVENTO_TRANSFERENCIA = "TransferenciaInventarioRegistrada"


@dataclass
class TransferirStockInput:
    producto_id: UUID
    sucursal_origen_id: UUID
    sucursal_destino_id: UUID
    cantidad: Decimal
    usuario_id: UUID
    referencia_id: UUID | None = None
    costo_unitario: Decimal | None = None
    motivo: str | None = None


class TransferirStockUseCase:
    """Registra una transferencia entre sucursales como DOS movimientos atómicos:
    una SALIDA en origen y una ENTRADA en destino. Ninguna operación hace commit:
    el llamador (router) confirma una sola transacción, de modo que si el paso de
    destino falla, el descuento en origen se revierte."""

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

    async def ejecutar(self, data: TransferirStockInput) -> None:
        if data.sucursal_origen_id == data.sucursal_destino_id:
            raise TransferenciaInvalida("La sucursal de origen y destino no pueden ser la misma.")
        if data.cantidad is None or data.cantidad <= 0:
            raise TransferenciaInvalida("La cantidad a transferir debe ser un número positivo.")

        producto = await self._producto_repo.obtener_por_id(data.producto_id)
        if not producto:
            raise ProductoNoEncontrado(f"No existe el producto {data.producto_id}")

        origen = await self._existencia_repo.obtener(data.producto_id, data.sucursal_origen_id)
        saldo_origen = origen.cantidad if origen else Decimal("0")
        nuevo_origen = saldo_origen - data.cantidad
        if nuevo_origen < 0 and not producto.permite_stock_negativo:
            raise StockInsuficiente(
                f"Stock insuficiente en sucursal origen para {producto.nombre}: "
                f"disponible {saldo_origen}, solicitado {data.cantidad}"
            )

        destino = await self._existencia_repo.obtener(data.producto_id, data.sucursal_destino_id)
        saldo_destino = destino.cantidad if destino else Decimal("0")
        nuevo_destino = saldo_destino + data.cantidad

        # --- Paso 1: SALIDA en origen ---
        mov_salida = MovimientoInventario.crear(
            producto_id=data.producto_id,
            sucursal_id=data.sucursal_origen_id,
            tipo=TipoMovimiento.TRANSFERENCIA,
            cantidad=data.cantidad,
            referencia_tipo="transferencia",
            usuario_id=data.usuario_id,
            referencia_id=data.referencia_id,
            costo_unitario=data.costo_unitario,
            motivo=data.motivo or f"Transferencia a sucursal {data.sucursal_destino_id}",
        )
        await self._movimiento_repo.guardar(mov_salida)
        if origen:
            await self._existencia_repo.actualizar_cantidad(
                data.producto_id, data.sucursal_origen_id, nuevo_origen
            )
        else:
            await self._existencia_repo.crear(Existencia(
                id=uuid4(), producto_id=data.producto_id, sucursal_id=data.sucursal_origen_id,
                cantidad=nuevo_origen, stock_minimo=Decimal("0"), stock_maximo=None,
            ))

        # --- Paso 2: ENTRADA en destino (misma transacción) ---
        mov_entrada = MovimientoInventario.crear(
            producto_id=data.producto_id,
            sucursal_id=data.sucursal_destino_id,
            tipo=TipoMovimiento.TRANSFERENCIA,
            cantidad=data.cantidad,
            referencia_tipo="transferencia",
            usuario_id=data.usuario_id,
            referencia_id=mov_salida.id,
            costo_unitario=data.costo_unitario,
            motivo=data.motivo or f"Transferencia desde sucursal {data.sucursal_origen_id}",
        )
        await self._movimiento_repo.guardar(mov_entrada)
        if destino:
            await self._existencia_repo.actualizar_cantidad(
                data.producto_id, data.sucursal_destino_id, nuevo_destino
            )
        else:
            await self._existencia_repo.crear(Existencia(
                id=uuid4(), producto_id=data.producto_id, sucursal_id=data.sucursal_destino_id,
                cantidad=nuevo_destino, stock_minimo=Decimal("0"), stock_maximo=None,
            ))

        if self._event_port is not None:
            await self._event_port.publicar(EVENTO_TRANSFERENCIA, {
                "usuario_id": data.usuario_id,
                "modulo": "inventario",
                "accion": "movimiento_transferencia",
                "entidad": "MovimientoInventario",
                "entidad_id": str(mov_salida.id),
                "detalle": {
                    "producto_id": str(data.producto_id),
                    "sucursal_origen_id": str(data.sucursal_origen_id),
                    "sucursal_destino_id": str(data.sucursal_destino_id),
                    "cantidad": str(data.cantidad),
                    "saldo_origen_anterior": str(saldo_origen),
                    "saldo_origen_nuevo": str(nuevo_origen),
                    "saldo_destino_anterior": str(saldo_destino),
                    "saldo_destino_nuevo": str(nuevo_destino),
                    "motivo": data.motivo,
                },
            })
