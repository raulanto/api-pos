from dataclasses import dataclass, field
from decimal import Decimal
from uuid import UUID
from typing import List

from app.modules.ventas.domain.entities import Devolucion, DevolucionLinea, Venta
from app.modules.ventas.domain.value_objects import EstadoVenta, MetodoDevolucion
from app.modules.ventas.domain.exceptions import (
    VentaNoEncontrada, VentaNoDevolvible, CantidadDevolucionExcedida,
    DevolucionInvalida, AnulacionNoPermitida, TurnoNoEncontrado,
)
from app.modules.ventas.application.ports.venta_repository import VentaRepository
from app.modules.ventas.application.ports.devolucion_repository import DevolucionRepository
from app.modules.ventas.application.ports.caja_repository import CajaTurnoRepository
from app.modules.ventas.application.ports.inventario_port import InventarioPort
from app.modules.ventas.application.ports.event_port import EventPort
from app.modules.ventas.application.ports.monedero_port import MonederoPort
from app.modules.clientes.application.ports.cliente_repository import ClienteRepository

_CENT = Decimal("0.01")


@dataclass
class DevolverVentaLineaInput:
    detalle_venta_id: UUID
    cantidad: Decimal


@dataclass
class DevolverVentaInput:
    venta_id: UUID
    caja_turno_id: UUID
    usuario_id: UUID
    metodo_devolucion: MetodoDevolucion
    lineas: List[DevolverVentaLineaInput] = field(default_factory=list)
    motivo: str | None = None
    # True para admin/gerente: puede devolver sobre turnos cerrados / ajenos.
    puede_turno_cerrado: bool = False
    idempotency_key: str | None = None


class DevolverVentaUseCase:
    """Devolución (parcial o total) de una venta, todo en la misma transacción:
    repone el stock de lo devuelto, ajusta el crédito si corresponde, registra la
    `Devolucion` y recalcula el estado de la venta."""

    def __init__(
        self,
        venta_repo: VentaRepository,
        devolucion_repo: DevolucionRepository,
        caja_repo: CajaTurnoRepository,
        inventario: InventarioPort,
        cliente_repo: ClienteRepository,
        event_port: EventPort,
        monedero: MonederoPort | None = None,
    ):
        self._venta_repo = venta_repo
        self._devolucion_repo = devolucion_repo
        self._caja_repo = caja_repo
        self._inventario = inventario
        self._cliente_repo = cliente_repo
        self._event_port = event_port
        self._monedero = monedero

    async def ejecutar(self, data: DevolverVentaInput) -> Devolucion:
        if data.idempotency_key:
            previa = await self._devolucion_repo.obtener_por_idempotency_key(data.idempotency_key)
            if previa is not None:
                return previa

        venta = await self._venta_repo.obtener_por_id(data.venta_id)
        if venta is None:
            raise VentaNoEncontrada(f"No existe la venta {data.venta_id}")
        if venta.estado in (EstadoVenta.CANCELADA, EstadoVenta.DEVUELTA_TOTAL):
            raise VentaNoDevolvible(
                f"La venta {venta.id} está {venta.estado.value}: no admite devoluciones."
            )

        turno = await self._caja_repo.obtener_por_id(data.caja_turno_id)
        if turno is None:
            raise TurnoNoEncontrado(f"No existe el turno {data.caja_turno_id}")
        if not data.puede_turno_cerrado:
            propio_y_abierto = turno.usuario_id == data.usuario_id and turno.esta_abierto
            if not propio_y_abierto:
                raise AnulacionNoPermitida(
                    "Sólo podés devolver en tu turno abierto; para turnos cerrados o "
                    "ajenos se requiere rol de gerente/admin."
                )

        if not data.lineas:
            raise DevolucionInvalida("Indicá al menos una línea a devolver.")

        por_id = {l.id: l for l in venta.lineas}
        dev_lineas: list[DevolucionLinea] = []
        aplicado: dict[UUID, Decimal] = {}
        for entrada in data.lineas:
            detalle = por_id.get(entrada.detalle_venta_id)
            if detalle is None:
                raise DevolucionInvalida(
                    f"La línea {entrada.detalle_venta_id} no pertenece a la venta {venta.id}."
                )
            cant = Decimal(str(entrada.cantidad))
            if cant <= 0:
                raise DevolucionInvalida("La cantidad a devolver debe ser mayor a 0.")
            ya = aplicado.get(detalle.id, Decimal("0"))
            if cant + ya > detalle.cantidad_devolvible:
                raise CantidadDevolucionExcedida(
                    f"La línea permite devolver {detalle.cantidad_devolvible - ya} más; "
                    f"pediste {cant}."
                )
            aplicado[detalle.id] = ya + cant
            monto = (detalle.precio_neto_unitario * cant).quantize(_CENT)
            dev_lineas.append(DevolucionLinea.crear(detalle.id, cant, monto))

        devolucion = Devolucion.crear(
            venta_id=venta.id,
            caja_turno_id=data.caja_turno_id,
            usuario_id=data.usuario_id,
            metodo_devolucion=data.metodo_devolucion,
            lineas=dev_lineas,
            motivo=data.motivo,
            idempotency_key=data.idempotency_key,
        )

        # 1) Stock: ENTRADA de lo devuelto (en unidad base), por línea.
        for entrada, dl in zip(data.lineas, dev_lineas):
            detalle = por_id[entrada.detalle_venta_id]
            cantidad_base = await self._inventario.convertir_a_base(
                producto_id=detalle.producto_id,
                cantidad=dl.cantidad,
                producto_unidad_id=detalle.producto_unidad_id,
            )
            await self._inventario.reponer_parcial(
                venta_id=venta.id,
                producto_id=detalle.producto_id,
                cantidad_base=cantidad_base,
                sucursal_id=venta.sucursal_id,
                devolucion_id=devolucion.id,
                usuario_id=data.usuario_id,
            )

        # 2) Dinero según el método:
        #   - credito  -> baja la deuda del cliente
        #   - monedero -> reintegra al monedero del teléfono de la venta
        #   - efectivo/tarjeta -> sólo queda registrado (el arqueo mira efectivo)
        credito_revertido = Decimal("0")
        if data.metodo_devolucion == MetodoDevolucion.CREDITO and venta.cliente_id is not None:
            credito_revertido = min(devolucion.monto_devuelto, venta.saldo_pendiente)
            if credito_revertido > 0:
                await self._cliente_repo.decrementar_saldo(venta.cliente_id, credito_revertido)
        elif data.metodo_devolucion == MetodoDevolucion.MONEDERO:
            if not venta.telefono:
                raise DevolucionInvalida(
                    "La venta no tiene teléfono asociado; no se puede devolver al monedero."
                )
            if self._monedero is not None:
                await self._monedero.reintegrar(
                    venta.telefono, devolucion.monto_devuelto, venta.id,
                    data.usuario_id, "devolución de venta",
                )

        # 3) Persistir devolución + acumulado por línea + estado de la venta.
        await self._devolucion_repo.crear(devolucion)
        for detalle_id, cant in aplicado.items():
            por_id[detalle_id].cantidad_devuelta += cant
        venta.recalcular_estado_devolucion()
        await self._venta_repo.registrar_devolucion(venta)

        await self._event_port.publicar("VentaDevuelta", {
            "usuario_id": data.usuario_id,
            "modulo": "ventas",
            "accion": "devolver_venta",
            "entidad": "Venta",
            "entidad_id": str(venta.id),
            "detalle": {
                "venta_id": str(venta.id),
                "devolucion_id": str(devolucion.id),
                "caja_turno_id": str(data.caja_turno_id),
                "monto_devuelto": str(devolucion.monto_devuelto),
                "metodo_devolucion": data.metodo_devolucion.value,
                "credito_revertido": str(credito_revertido),
                "estado_venta": venta.estado.value,
            },
        })
        return devolucion
