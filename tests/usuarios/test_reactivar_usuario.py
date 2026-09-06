"""Tests de `ReactivarUsuarioUseCase` (alta de un usuario dado de baja)."""
import uuid
from datetime import datetime, timezone

import pytest

from app.modules.usuarios.application.use_cases.reactivar_usuario import (
    ReactivarUsuarioUseCase,
)
from app.modules.usuarios.domain.entities import Usuario
from app.modules.usuarios.domain.exceptions import UsuarioNoEncontrado


class _UsuarioRepo:
    def __init__(self, usuario=None):
        self._usuario = usuario
        self.guardado = None

    async def obtener_por_id(self, uid, includes=frozenset()):
        return self._usuario

    async def guardar(self, usuario):
        self.guardado = usuario


def _usuario(activo: bool) -> Usuario:
    return Usuario(
        id=uuid.uuid4(),
        sucursal_id=None,
        rol_id=uuid.uuid4(),
        nombre="Ana",
        email="ana@example.com",
        password_hash="x",
        activo=activo,
        created_at=datetime.now(timezone.utc),
    )


async def test_usuario_inexistente():
    with pytest.raises(UsuarioNoEncontrado):
        await ReactivarUsuarioUseCase(_UsuarioRepo(usuario=None)).ejecutar(uuid.uuid4())


async def test_reactiva_usuario_inactivo():
    repo = _UsuarioRepo(usuario=_usuario(activo=False))
    resultado = await ReactivarUsuarioUseCase(repo).ejecutar(uuid.uuid4())
    assert resultado.activo is True
    assert repo.guardado is resultado


async def test_idempotente_si_ya_esta_activo():
    repo = _UsuarioRepo(usuario=_usuario(activo=True))
    resultado = await ReactivarUsuarioUseCase(repo).ejecutar(uuid.uuid4())
    assert resultado.activo is True
    assert repo.guardado is None  # no reescribe
