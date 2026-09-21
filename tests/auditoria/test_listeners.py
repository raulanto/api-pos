"""Tests para los listeners de eventos de auditoría."""
import uuid
import pytest
from unittest.mock import MagicMock

from app.modules.auditoria.infrastructure.listeners import registrar_auditoria
from app.modules.auditoria.infrastructure.persistence.orm_models import LogAuditoriaORM


@pytest.mark.asyncio
async def test_registrar_auditoria_listener():
    db_mock = MagicMock()
    user_id = uuid.uuid4()
    entidad_id = uuid.uuid4()

    payload = {
        "usuario_id": user_id,
        "modulo": "ventas",
        "accion": "crear_venta",
        "entidad": "Venta",
        "entidad_id": entidad_id,
        "detalle": {"total": 500.0},
    }

    await registrar_auditoria(payload, db_mock)

    assert db_mock.add.called
    log_guardado = db_mock.add.call_args[0][0]
    assert isinstance(log_guardado, LogAuditoriaORM)
    assert log_guardado.usuario_id == user_id
    assert log_guardado.modulo == "ventas"
    assert log_guardado.accion == "crear_venta"
    assert log_guardado.entidad == "Venta"
    assert log_guardado.entidad_id == str(entidad_id)
    assert log_guardado.detalle == {"total": 500.0}
