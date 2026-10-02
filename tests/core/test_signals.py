import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.signals import signal_manager
from app.shared.events import event_bus


@pytest.mark.asyncio
async def test_signal_manager_emitir():
    modulo = "agenda"
    payload = {
        "usuario_id": uuid.uuid4(),
        "modulo": modulo,
        "accion": "CitaCreada",
        "entidad": "Cita",
        "entidad_id": str(uuid.uuid4()),
        "detalle": {"paciente": "Maria", "password": "secret_pass"},
    }

    # Publicar un evento en el bus debe llamar a retransmitir_como_senal
    # Probar que event_bus dispara hacia la función sin lanzar errores.
    await event_bus.publicar("CitaCreada", payload, db=None)


def test_websocket_signals_endpoint():
    client = TestClient(app)
    with client.websocket_connect("/api/v1/signals/ws/agenda") as websocket:
        # Emitir señal mientras la conexión está activa
        payload = {
            "modulo": "agenda",
            "accion": "CitaCreada",
            "entidad": "Cita",
            "entidad_id": str(uuid.uuid4()),
            "detalle": {"paciente": "Carlos", "password": "secret_pass"},
        }
        
        # Invocación sincrónica dentro del test
        import asyncio
        asyncio.run(signal_manager.emitir_modulo("agenda", "CitaCreada", payload))
        
        data = websocket.receive_json()
        assert data["modulo"] == "agenda"
        assert data["evento"] == "CitaCreada"
        assert data["data"]["detalle"]["paciente"] == "Carlos"
        assert data["data"]["detalle"]["password"] == "********"
