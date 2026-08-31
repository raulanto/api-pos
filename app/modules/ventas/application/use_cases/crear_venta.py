from dataclasses import dataclass
from uuid import UUID
from decimal import Decimal
from typing import List

from app.modules.ventas.domain.entities import Venta, DetalleVenta, Pago
from app.modules.ventas.domain.value_objects import EstadoVenta, MetodoPago
from app.modules.ventas.domain.exceptions import (
    CajaNoAbierta, VentaCreditoSinCliente, TurnoDeOtraSucursal,
)
from app.modules.ventas.application.ports.venta_repository import VentaRepository
from app.modules.ventas.application.ports.caja_repository import CajaTurnoRepository
from app.modules.ventas.application.ports.inventario_port import InventarioPort
from app.modules.ventas.application.ports.event_port import EventPort
from app.modules.clientes.application.ports.cliente_repository import ClienteRepository
from app.modules.clientes.domain.exceptions import ClienteNoEncontrado

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
    idempotency_key: str | None = None

class CrearVentaUseCase:
    def __init__(
        self,
        venta_repo: VentaRepository,
        caja_repo: CajaTurnoRepository,
        inventario: InventarioPort,
        cliente_repo: ClienteRepository,
        event_port: EventPort
    ):
        self._venta_repo = venta_repo
        self._caja_repo = caja_repo
        self._inventario = inventario
        self._cliente_repo = cliente_repo
        self._event_port = event_port

    async def ejecutar(self, data: CrearVentaInput) -> Venta:
        # Idempotencia: si ya se procesó esta clave, devolver la venta existente.
        if data.idempotency_key:
            previa = await self._venta_repo.obtener_por_idempotency_key(data.idempotency_key)
            if previa is not None:
                return previa

        turno = await self._caja_repo.obtener_por_id(data.caja_turno_id)
        if turno is None or not turno.esta_abierto:
            raise CajaNoAbierta("No hay un turno de caja abierto para esta sucursal")
        if turno.sucursal_id != data.sucursal_id:
            raise TurnoDeOtraSucursal(
                "El turno de caja indicado no pertenece a la sucursal del usuario"
            )

        lineas = [
            DetalleVenta.crear(
                producto_id=l.producto_id,
                cantidad=l.cantidad,
                precio_unitario=l.precio_unitario,
                descuento_linea=l.descuento_linea,
                impuesto_tasa=l.impuesto_tasa,
            )
            for l in data.lineas
        ]
        pagos = [Pago.crear(monto=p.monto, metodo_pago=p.metodo_pago) for p in data.pagos]

        venta = Venta.crear(
            sucursal_id=data.sucursal_id,
            caja_turno_id=data.caja_turno_id,
            usuario_id=data.usuario_id,
            cliente_id=data.cliente_id,
            lineas=lineas,
            pagos=pagos,
            descuento_total=data.descuento_total,
            idempotency_key=data.idempotency_key,
        )

        if venta.saldo_pendiente > Decimal("0"):
            if venta.cliente_id is None:
                raise VentaCreditoSinCliente(
                    "No se puede dejar saldo pendiente en una venta sin cliente registrado"
                )
            cliente = await self._cliente_repo.obtener_por_id(venta.cliente_id)
            if cliente is None:
                raise ClienteNoEncontrado(f"No existe el cliente {venta.cliente_id}")
            # Única fuente de verdad de la regla de crédito: la entidad valida y
            # lanza LimiteCreditoExcedido si el saldo pendiente no cabe.
            cliente.incrementar_saldo(venta.saldo_pendiente)
            venta.estado = EstadoVenta.PENDIENTE_PAGO
            await self._cliente_repo.incrementar_saldo(venta.cliente_id, venta.saldo_pendiente)
        else:
            venta.estado = EstadoVenta.PAGADA

        await self._venta_repo.guardar(venta)

        # Mismo request => misma transacción: si una línea deja stock negativo,
        # StockInsuficiente sube y get_db() revierte TODO (venta incluida).
        for linea in venta.lineas:
            await self._inventario.descontar_stock(
                producto_id=linea.producto_id,
                sucursal_id=data.sucursal_id,
                cantidad=linea.cantidad,
                referencia_venta_id=venta.id,
                usuario_id=data.usuario_id,
            )

        await self._event_port.publicar("VentaCreada", {
            "usuario_id": data.usuario_id,
            "modulo": "ventas",
            "accion": "crear_venta",
            "entidad": "Venta",
            "entidad_id": str(venta.id),
            "detalle": {
                "venta_id": str(venta.id),
                "sucursal_id": str(data.sucursal_id),
                "caja_turno_id": str(data.caja_turno_id),
                "total": str(venta.total),
                "estado": venta.estado.value,
            },
        })

        return venta
