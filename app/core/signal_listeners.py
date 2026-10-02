from typing import Any
from app.core.signals import signal_manager
from app.shared.events import event_bus

CAMPOS_SENSIBLES = {
    "password", "password_plano", "password_hash", "token", "refresh_token",
    "access_token", "secret", "jwt_secret", "pin", "cvv", "tarjeta", "card_number",
}


def _sanitizar_payload(valor: Any) -> Any:
    """Sanitiza recursivamente datos sensibles del payload antes de transmitirlos por WebSocket."""
    if isinstance(valor, dict):
        limpio = {}
        for k, v in valor.items():
            if isinstance(k, str) and k.lower() in CAMPOS_SENSIBLES:
                limpio[k] = "********"
            else:
                limpio[k] = _sanitizar_payload(v)
        return limpio
    elif isinstance(valor, list):
        return [_sanitizar_payload(item) for item in valor]
    return valor


async def retransmitir_como_senal(payload: dict, db: Any = None) -> None:
    """
    Listener que se suscribe al event_bus y emite la señal
    a través del SignalManager hacia los WebSockets del módulo indicado.
    """
    modulo = payload.get("modulo")
    accion = payload.get("accion")
    if not modulo or not accion:
        return

    payload_sanitizado = _sanitizar_payload(payload)
    await signal_manager.emitir_modulo(
        modulo=modulo,
        evento=accion,
        payload=payload_sanitizado,
    )


def registrar_signal_listeners() -> None:
    """
    Registra el handler retransmitir_como_senal para todos los eventos clave
    de los módulos del sistema.
    """
    eventos = [
        # Ventas y Caja
        "VentaCreada", "VentaAnulada", "DescuentoManualAplicado",
        "CajaTurnoAbierto", "CajaTurnoCerrado", "MovimientoCajaRegistrado", "TurnoConciliado",
        # Inventario
        "MovimientoInventarioRegistrado", "TransferenciaInventarioRegistrada",
        "ProductoCreado", "ProductoEditado", "ProductoDesactivado",
        "CategoriaCreada", "CategoriaEditada",
        # Usuarios, Clientes, Proveedores, Promociones, Sucursales
        "UsuarioCreado", "UsuarioEditado", "UsuarioDesactivado", "UsuarioReactivado",
        "ClienteCreado", "ClienteEditado",
        "ProveedorCreado", "ProveedorEditado",
        "PromocionCreada", "PromocionEditada",
        "SucursalCreada", "SucursalEditada",
        # Pedidos y Agenda
        "PedidoCreado", "PedidoConfirmado", "PedidoCancelado", "PedidoReabierto",
        "PedidoEntregaActualizada", "PedidoAnticipoRegistrado", "PedidoServiciosAsignados", "PedidoFacturado",
        "CitaCreada", "CitaConfirmada", "CitaCancelada", "CitaReagendada", "CitaFacturada",
    ]
    for ev in eventos:
        event_bus.suscribir(ev, retransmitir_como_senal)
