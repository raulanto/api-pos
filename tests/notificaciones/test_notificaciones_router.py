import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.dependencies import get_current_user
from app.modules.usuarios.infrastructure.persistence.orm_models import UsuarioORM
from app.modules.notificaciones.domain.entities import Notificacion, TipoNotificacion
from app.modules.notificaciones.infrastructure.api.router import _get_service
from app.modules.notificaciones.application.use_cases.gestionar_notificaciones import NotificacionesUseCase
from tests.notificaciones.test_notificaciones_use_cases import InMemoryNotificacionRepository


def test_api_notificaciones_endpoints():
    fake_repo = InMemoryNotificacionRepository()
    use_case = NotificacionesUseCase(fake_repo)

    user_id = uuid.uuid4()
    mock_user = UsuarioORM(id=user_id, email="emp@pos.local", nombre="Empleado")

    n1 = Notificacion.crear(user_id, "agenda", TipoNotificacion.OFERTA_CITA, "Oferta", "Mensaje 1")
    n2 = Notificacion.crear(user_id, "agenda", TipoNotificacion.CITA_ASIGNADA, "Cita", "Mensaje 2")
    fake_repo.items[str(n1.id)] = n1
    fake_repo.items[str(n2.id)] = n2

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[_get_service] = lambda: use_case

    client = TestClient(app)

    try:
        # 1. Resumen
        res = client.get("/api/v1/notificaciones/resumen")
        assert res.status_code == 200
        assert res.json()["data"]["unread_count"] == 2

        # 2. Listar
        res_list = client.get("/api/v1/notificaciones?leida=false")
        assert res_list.status_code == 200
        assert len(res_list.json()["data"]) == 2

        # 3. Marcar leída
        res_patch = client.patch(f"/api/v1/notificaciones/{n1.id}/marcar-leida")
        assert res_patch.status_code == 200
        assert res_patch.json()["data"]["leida"] is True

        # 4. Marcar todas leídas
        res_todas = client.patch("/api/v1/notificaciones/marcar-todas-leidas")
        assert res_todas.status_code == 200
        assert res_todas.json()["data"]["count"] == 1

    finally:
        app.dependency_overrides.clear()
