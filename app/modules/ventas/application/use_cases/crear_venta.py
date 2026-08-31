from dataclasses import dataclass
from uuid import UUID
from decimal import Decimal
from typing import List

from app.modules.ventas.domain.entities import Venta, DetalleVenta, Pago
from app.modules.ventas.domain.value_objects import EstadoVenta, MetodoPago
from app.modules.ventas.domain.exceptions import CajaNoAbierta, VentaCreditoSinCliente
from app.modules.ventas.application.ports.venta_repository import VentaRepository
from app.modules.ventas.application.ports.caja_repository import CajaTurnoRepository
from app.modules.ventas.application.ports.inventario_port import InventarioPort
from app.modules.clientes.application.ports.cliente_repository import ClienteRepository
from app.modules.clientes.domain.exceptions import LimiteCreditoExcedido

@dataclass
class LineaInput:
    producto_id: UUID
    cantidad: Decimal
    precio_unitario: Decimal
    descuento_linea: Decimal = Decimal("0")
    impuesto_tasa: Decimal = Decimal("0")

@dataclass
class PagoInput:
    monto: Decimal
    metodo_pago: MetodoPago

@dataclass
class CrearVentaInput:
    sucursal_id: UUID
    caja_turno_id: UUID
    usuario_id: UUID
    cliente_id: UUID | None
    descuento_total: Decimal
    lineas: List[LineaInput]
    pagos: List[PagoInput]

class CrearVentaUseCase:
    def __init__(
        self,
        venta_repo: VentaRepository,
        caja_repo: CajaTurnoRepository,
        inventario: InventarioPort,
        cliente_repo: ClienteRepository
    ):
        self._venta_repo = venta_repo
        self._caja_repo = caja_repo
        self._inventario = inventario
        self._cliente_repo = cliente_repo

    async def ejecutar(self, data: CrearVentaInput) -> Venta:
        turno = await self._caja_repo.obtener_por_id(data.caja_turno_id)
        if turno is None or turno.estado != "abierto":
            raise CajaNoAbierta("No hay un turno de caja abierto para esta sucursal")

        lineas = [
            DetalleVenta.crear(
                producto_id=l.producto_id,
                cantidad=l.cantidad,
                precio_unitario=l.precio_unitario,
                descuento_linea=l.descuento_linea,
                impuesto_tasa=l.impuesto_tasa
            )
            for l in data.lineas
        ]

        pagos = [
            Pago.crear(monto=p.monto, metodo_pago=p.metodo_pago)
            for p in data.pagos
        ]

        venta = Venta.crear(
            sucursal_id=data.sucursal_id,
            caja_turno_id=data.caja_turno_id,
            usuario_id=data.usuario_id,
            cliente_id=data.cliente_id,
            lineas=lineas,
            pagos=pagos,
            descuento_total=data.descuento_total
        )

        if venta.saldo_pendiente > Decimal("0"):
            if venta.cliente_id is None:
                raise VentaCreditoSinCliente(
                    "No se puede dejar saldo pendiente en una venta sin cliente registrado"
                )
            
            cliente = await self._cliente_repo.obtener_por_id(venta.cliente_id)
            disponible = cliente.limite_credito - cliente.saldo_credito
            if venta.saldo_pendiente > disponible:
                raise LimiteCreditoExcedido(
                    f"Saldo pendiente {venta.saldo_pendiente} excede crédito disponible {disponible}"
                )
            
            venta.estado = EstadoVenta.PENDIENTE_PAGO
            await self._cliente_repo.incrementar_saldo(venta.cliente_id, venta.saldo_pendiente)
        else:
            venta.estado = EstadoVenta.PAGADA

        await self._venta_repo.guardar(venta)

        # Llama a InventarioPort. Esto debe ejecutar dentro de la misma transacción DB.
        for linea in venta.lineas:
            await self._inventario.descontar_stock(
                producto_id=linea.producto_id,
                sucursal_id=data.sucursal_id,
                cantidad=linea.cantidad,
                referencia_venta_id=venta.id,
                usuario_id=data.usuario_id
            )

        return venta
