from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from app.modules.ventas.application.use_cases.crear_venta import CrearVentaUseCase
from app.modules.ventas.application.ports.event_port import EventPort
from app.modules.ventas.domain.value_objects import MetodoPago
from app.modules.pedidos.application.ports.pedido_repository import PedidoRepository
from app.modules.pedidos.application.use_cases.actualizar_pedido import _FuentePrecio
from app.modules.pedidos.application.use_cases.crear_pedido import cotizar_a_detalles
from app.modules.pedidos.domain.entities import Pedido, PedidoPago
from app.modules.pedidos.domain.exceptions import PedidoNoEncontrado
from app.modules.pedidos.domain.value_objects import EstadoEntrega


async def _cargar(repo: PedidoRepository, pedido_id: UUID) -> Pedido:
    pedido = await repo.obtener_por_id(pedido_id)
    if pedido is None:
        raise PedidoNoEncontrado(f"No existe el pedido {pedido_id}")
    return pedido


def _evento(usuario_id: UUID, accion: str, pedido: Pedido, detalle: dict) -> dict:
    return {
        "usuario_id": usuario_id, "modulo": "pedidos", "accion": accion,
        "entidad": "Pedido", "entidad_id": str(pedido.id),
        "detalle": {"pedido_id": str(pedido.id), **detalle},
    }


class ConfirmarPedidoUseCase:
    """`borrador -> confirmado`. Refresca el snapshot de precios (mayoreo/promos
    vigentes al momento de aceptar) antes de congelar."""
    def __init__(self, pedido_repo: PedidoRepository, crear_venta_uc: CrearVentaUseCase,
                 event_port: EventPort):
        self._repo = pedido_repo
        self._venta_uc = crear_venta_uc
        self._event_port = event_port

    async def ejecutar(self, pedido_id: UUID, usuario_id: UUID) -> Pedido:
        pedido = await _cargar(self._repo, pedido_id)
        pedido.reemplazar_lineas(
            await cotizar_a_detalles(self._venta_uc, _FuentePrecio(pedido, None))
        )
        pedido.confirmar()
        await self._repo.actualizar(pedido)
        await self._event_port.publicar("PedidoConfirmado", _evento(
            usuario_id, "confirmar_pedido", pedido, {"total": str(pedido.total)},
        ))
        return pedido


class ReabrirPedidoUseCase:
    def __init__(self, pedido_repo: PedidoRepository, event_port: EventPort):
        self._repo = pedido_repo
        self._event_port = event_port

    async def ejecutar(self, pedido_id: UUID, usuario_id: UUID) -> Pedido:
        pedido = await _cargar(self._repo, pedido_id)
        pedido.reabrir()
        await self._repo.actualizar(pedido)
        await self._event_port.publicar("PedidoReabierto", _evento(
            usuario_id, "reabrir_pedido", pedido, {},
        ))
        return pedido


class CancelarPedidoUseCase:
    def __init__(self, pedido_repo: PedidoRepository, event_port: EventPort):
        self._repo = pedido_repo
        self._event_port = event_port

    async def ejecutar(self, pedido_id: UUID, usuario_id: UUID,
                       motivo: str | None = None) -> Pedido:
        pedido = await _cargar(self._repo, pedido_id)
        pedido.cancelar()
        reembolsos = pedido.marcar_anticipos_reembolsados()
        await self._repo.actualizar(pedido)
        if reembolsos:
            await self._repo.marcar_pagos_reembolsados(pedido.id)
            await self._event_port.publicar("PedidoReembolsoRequerido", _evento(
                usuario_id, "reembolsar_anticipo", pedido, {
                    "monto": str(sum((p.monto for p in reembolsos), Decimal("0"))),
                    "anticipos": [str(p.id) for p in reembolsos],
                },
            ))
        await self._event_port.publicar("PedidoCancelado", _evento(
            usuario_id, "cancelar_pedido", pedido,
            {"motivo": (motivo or "").strip() or None},
        ))
        return pedido


@dataclass
class CambiarEntregaInput:
    pedido_id: UUID
    usuario_id: UUID
    estado_entrega: EstadoEntrega | None = None
    repartidor_id: UUID | None = None
    motivo: str | None = None


class CambiarEntregaUseCase:
    """Asigna repartidor y/o avanza el estado de entrega (domicilio/recoger)."""
    def __init__(self, pedido_repo: PedidoRepository, event_port: EventPort):
        self._repo = pedido_repo
        self._event_port = event_port

    async def ejecutar(self, data: CambiarEntregaInput) -> Pedido:
        pedido = await _cargar(self._repo, data.pedido_id)
        if data.repartidor_id is not None:
            pedido.asignar_repartidor(data.repartidor_id)
        if data.estado_entrega is not None:
            pedido.avanzar_entrega(data.estado_entrega, motivo=data.motivo)
        await self._repo.actualizar(pedido)
        await self._event_port.publicar("PedidoEntregaActualizada", _evento(
            data.usuario_id, "actualizar_entrega", pedido, {
                "estado_entrega": pedido.estado_entrega.value if pedido.estado_entrega else None,
                "repartidor_id": str(pedido.repartidor_id) if pedido.repartidor_id else None,
            },
        ))
        return pedido


@dataclass
class RegistrarAnticipoInput:
    pedido_id: UUID
    usuario_id: UUID
    monto: Decimal
    metodo_pago: MetodoPago
    referencia: str | None = None


class RegistrarAnticipoUseCase:
    def __init__(self, pedido_repo: PedidoRepository, event_port: EventPort):
        self._repo = pedido_repo
        self._event_port = event_port

    async def ejecutar(self, data: RegistrarAnticipoInput) -> PedidoPago:
        pedido = await _cargar(self._repo, data.pedido_id)
        pago = PedidoPago.crear(data.monto, data.metodo_pago, data.referencia)
        pedido.agregar_anticipo(pago)
        await self._repo.agregar_pago(pago)
        await self._event_port.publicar("PedidoAnticipoRegistrado", _evento(
            data.usuario_id, "registrar_anticipo", pedido, {
                "monto": str(pago.monto), "metodo_pago": pago.metodo_pago.value,
            },
        ))
        return pago
