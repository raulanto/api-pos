"""Tests de endpoints del módulo de auditoría."""
import uuid
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.dependencies import get_current_user, UsuarioAutenticado
from app.modules.usuarios.domain.entities import Usuario
from app.modules.auditoria.infrastructure.api.router import get_auditoria_repo
from app.modules.auditoria.domain.entities import LogAuditoria
from app.shared.responses import Page, PageParams, Sort


class _FakeRepo:
    def __init__(self, log=None):
        self.log = log

    async def obtener_por_id(self, log_id: uuid.UUID, includes: frozenset[str] = frozenset()):
        if self.log and self.log.id == log_id:
            return self.log
        return None

    async def listar(self, filtro, paginacion: PageParams, orden: Sort, includes: frozenset[str] = frozenset()):
        items = [self.log] if self.log else []
        return Page(items=items, total=len(items))


def _usuario_con_permiso(permisos: list[str]) -> UsuarioAutenticado:
    u = Usuario(
        id=uuid.uuid4(),
        sucursal_id=None,
        rol_id=uuid.uuid4(),
        nombre="Test User",
        email="test@pos.local",
        password_hash="x",
    )
    return UsuarioAutenticado(
        usuario=u,
        rol_codigo="admin",
        permisos=frozenset(permisos),
    )


def test_listar_auditoria_endpoint():
    log = LogAuditoria.crear(
        usuario_id=uuid.uuid4(),
        modulo="ventas",
        accion="crear",
        entidad="Venta",
        entidad_id=str(uuid.uuid4()),
        detalle={"total": 150.0},
    )

    app.dependency_overrides[get_current_user] = lambda: _usuario_con_permiso(["auditoria.leer"])
    app.dependency_overrides[get_auditoria_repo] = lambda: _FakeRepo(log)

    client = TestClient(app)
    response = client.get("/api/v1/auditoria?modulo=ventas")
    app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert len(body["data"]) == 1
    assert body["data"][0]["modulo"] == "ventas"


def test_obtener_log_endpoint_exito():
    log_id = uuid.uuid4()
    log = LogAuditoria(
        id=log_id,
        usuario_id=uuid.uuid4(),
        modulo="caja",
        accion="abrir_turno",
        entidad="CajaTurno",
        entidad_id=str(uuid.uuid4()),
        detalle=None,
        ip_address=None,
        fecha=datetime.now(timezone.utc),
    )

    app.dependency_overrides[get_current_user] = lambda: _usuario_con_permiso(["auditoria.leer"])
    app.dependency_overrides[get_auditoria_repo] = lambda: _FakeRepo(log)

    client = TestClient(app)
    response = client.get(f"/api/v1/auditoria/{log_id}")
    app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["id"] == str(log_id)
    assert body["data"]["modulo"] == "caja"


def test_obtener_log_endpoint_404():
    app.dependency_overrides[get_current_user] = lambda: _usuario_con_permiso(["auditoria.leer"])
    app.dependency_overrides[get_auditoria_repo] = lambda: _FakeRepo(log=None)

    client = TestClient(app)
    response = client.get(f"/api/v1/auditoria/{uuid.uuid4()}")
    app.dependency_overrides.clear()

    assert response.status_code == 404
