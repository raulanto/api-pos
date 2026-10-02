from typing import Dict, List
from fastapi import WebSocket


class SignalManager:
    """Gestor global de conexiones WebSocket clasificadas por módulo."""

    def __init__(self):
        self._active_connections: Dict[str, List[WebSocket]] = {}

    async def conectar(self, modulo: str, websocket: WebSocket) -> None:
        """Acepta la conexión WebSocket y la registra en la lista del módulo."""
        await websocket.accept()
        if modulo not in self._active_connections:
            self._active_connections[modulo] = []
        self._active_connections[modulo].append(websocket)

    def desconectar(self, modulo: str, websocket: WebSocket) -> None:
        """Remueve la conexión WebSocket del módulo correspondiente."""
        if modulo in self._active_connections:
            if websocket in self._active_connections[modulo]:
                self._active_connections[modulo].remove(websocket)
            if not self._active_connections[modulo]:
                del self._active_connections[modulo]

    async def emitir_modulo(self, modulo: str, evento: str, payload: dict) -> None:
        """
        Transmite un mensaje JSON a todas las conexiones activas registradas en un módulo.
        Remueve automáticamente sockets cerrados o defectuosos.
        """
        conexiones = list(self._active_connections.get(modulo, []))
        if not conexiones:
            return

        from app.core.signal_listeners import _sanitizar_payload
        payload_limpio = _sanitizar_payload(payload)

        mensaje = {
            "modulo": modulo,
            "evento": evento,
            "data": payload_limpio,
        }

        desconectados = []
        for ws in conexiones:
            try:
                await ws.send_json(mensaje)
            except Exception:
                desconectados.append(ws)

        for ws in desconectados:
            self.desconectar(modulo, ws)


signal_manager = SignalManager()
