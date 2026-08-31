from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from app.modules.ventas.domain.entities import Venta
from app.modules.ventas.domain.value_objects import EstadoVenta
from app.modules.ventas.domain.exceptions import VentaNoEncontrada, AnulacionNoPermitida
from app.modules.ventas.application.ports.venta_repository import VentaRepository
from app.modules.ventas.application.ports.caja_repository import CajaTurnoRepository
from app.modules.ventas.application.ports.inventario_port import InventarioPort
from app.modules.ventas.application.ports.event_port import EventPort
from app.modules.clientes.application.ports.cliente_repository import ClienteRepository


@dataclass
class AnularVentaInput:
    venta_id: UUID
    usuario_id: UUID
    motivo: str | None = None
    # True para admin/gerente: puede anular ventas de turnos ya cerrados o de otros cajeros.
    puede_anular_cerradas: bool = False


class AnularVentaUseCase:
    """Anula una venta con efectos en cascada, todo en la misma transacción:
    revierte el stock de cada línea y el crédito consumido, y marca la venta
    como CANCELADA. Si falla la reversión de stock, nada queda anulado."""

    def __init__(
        self,
        venta_repo: VentaRepository,
        caja_repo: CajaTurnoRepository,
        inventario: InventarioPort,
        cliente_repo: ClienteRepository,
        event_port: EventPort,
    ):
        self._venta_repo = venta_repo
        self._caja_repo = caja_repo
        self._inventario = inventario
        self._cliente_repo = cliente_repo
        self._event_port = event_port

    async def ejecutar(self, data: AnularVentaInput) -> Venta:
        venta = await self._venta_repo.obtener_por_id(data.venta_id)
        if venta is None:
            raise VentaNoEncontrada(f"No existe la venta {data.venta_id}")

        # Regla: el cajero sólo anula ventas propias mientras su turno siga abierto.
        # Anular ventas de turnos cerrados o ajenas requiere rol global.
        if not data.puede_anular_cerradas:
            turno = await self._caja_repo.obtener_por_id(venta.caja_turno_id)
            propia_y_turno_abierto = (
                venta.usuario_id == data.usuario_id and turno is not None and turno.esta_abierto
            )
            if not propia_y_turno_abierto:
                raise AnulacionNoPermitida(
                    "Sólo podés anular tus ventas del turno abierto; para anular ventas de "
                    "turnos cerrados se requiere rol de gerente/admin."
                )

        # Valida que no esté ya cancelada (lanza VentaYaCancelada).
        venta.cancelar()

        # 1) Revertir stock por línea (movimiento de ENTRADA).
        for linea in venta.lineas:
            await self._inventario.reingresar_stock(
                producto_id=linea.producto_id,
                sucursal_id=venta.sucursal_id,
                cantidad=linea.cantidad,
                referencia_venta_id=venta.id,
                usuario_id=data.usuario_id,
            )

        # 2) Revertir crédito consumido, si la venta dejó saldo a crédito.
        credito_revertido = Decimal("0")
        if venta.cliente_id is not None and venta.saldo_pendiente > Decimal("0"):
            credito_revertido = venta.saldo_pendiente
            await self._cliente_repo.decrementar_saldo(venta.cliente_id, credito_revertido)

        # 3) Persistir el nuevo estado.
        await self._venta_repo.actualizar_estado(venta.id, EstadoVenta.CANCELADA)

        await self._event_port.publicar("VentaAnulada", {
            "usuario_id": data.usuario_id,
            "modulo": "ventas",
            "accion": "anular_venta",
            "entidad": "Venta",
            "entidad_id": str(venta.id),
            "detalle": {
                "venta_id": str(venta.id),
                "sucursal_id": str(venta.sucursal_id),
                "caja_turno_id": str(venta.caja_turno_id),
                "credito_revertido": str(credito_revertido),
                "lineas_revertidas": len(venta.lineas),
                "motivo": data.motivo,
            },
        })

        return venta
