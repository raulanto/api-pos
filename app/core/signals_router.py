from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status, Query
import uuid

from app.core.security import decode_access_token
from app.core.signals import signal_manager

router = APIRouter()


@router.websocket("/ws/{modulo}")
async def websocket_signals_endpoint(
    websocket: WebSocket,
    modulo: str,
    token: Optional[str] = Query(default=None),
):
    """
    Endpoint WebSocket para recibir señales en tiempo real por módulo.
    Ejemplo URL: ws://localhost:8000/api/v1/signals/ws/agenda?token=...
    """
    if token:
        payload = decode_access_token(token)
        if not payload or "sub" not in payload:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

    await signal_manager.conectar(modulo, websocket)
    try:
        while True:
            # Escuchar pings o mensajes entrantes del cliente para mantener conexión activa
            await websocket.receive_text()
    except WebSocketDisconnect:
        signal_manager.desconectar(modulo, websocket)
    except Exception:
        signal_manager.desconectar(modulo, websocket)
