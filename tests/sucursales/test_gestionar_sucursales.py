"""Tests de los casos de uso del módulo sucursales (fakes en memoria)."""
import uuid
from datetime import datetime, timezone

import pytest

from app.modules.sucursales.domain.entities import Sucursal, TipoSucursal
from app.modules.sucursales.domain.exceptions import (
    SucursalNoEncontrada, NombreSucursalDuplicado, CodigoSucursalDuplicado,
    SucursalConUsuariosActivos, SucursalPadreNoEncontrada, JerarquiaSucursalInvalida,
)
from app.modules.sucursales.application.use_cases.gestionar_sucursales import (
    CrearSucursalUseCase, CrearSucursalInput,
    ActualizarSucursalUseCase, ActualizarSucursalInput,
    DesactivarSucursalUseCase,
)


def _suc(nombre="Central", codigo=None, padre_id=None) -> Sucursal:
    return Sucursal(
        id=uuid.uuid4(), nombre=nombre, direccion="Calle 1", telefono="555",
        activo=True, created_at=datetime.now(timezone.utc),
        tipo=TipoSucursal.TIENDA, codigo=codigo, sucursal_padre_id=padre_id,
    )


class _Repo:
    def __init__(self, sucursales=None, con_usuarios=False):
        self._por_id = {s.id: s for s in (sucursales or [])}
        self._con_usuarios = con_usuarios
        self.creadas = []
        self.actualizadas = []

    async def obtener_por_id(self, sid):
        return self._por_id.get(sid)

    async def obtener_por_nombre(self, nombre):
        for s in self._por_id.values():
            if s.nombre.lower() == nombre.strip().lower():
                return s
        return None

    async def obtener_por_codigo(self, codigo):
        for s in self._por_id.values():
            if s.codigo and s.codigo.lower() == codigo.strip().lower():
                return s
        return None

    async def crear(self, sucursal):
        self.creadas.append(sucursal)
        self._por_id[sucursal.id] = sucursal
        return sucursal

    async def actualizar(self, sucursal):
        self.actualizadas.append(sucursal)
        self._por_id[sucursal.id] = sucursal

    async def tiene_usuarios_activos(self, sid):
        return self._con_usuarios


async def test_crear_ok():
    repo = _Repo()
    s = await CrearSucursalUseCase(repo).ejecutar(CrearSucursalInput(
        nombre="Tienda Centro", direccion="Av 5", telefono="123",
        tipo=TipoSucursal.TIENDA, codigo="TDA-01",
    ))
    assert s.codigo == "TDA-01"
    assert repo.creadas == [s]


async def test_crear_codigo_duplicado():
    existente = _suc(nombre="Otra", codigo="TDA-01")
    repo = _Repo([existente])
    with pytest.raises(CodigoSucursalDuplicado):
        await CrearSucursalUseCase(repo).ejecutar(CrearSucursalInput(
            nombre="Nueva", direccion="x", telefono="y", codigo="tda-01",
        ))


async def test_crear_nombre_duplicado():
    repo = _Repo([_suc(nombre="Central")])
    with pytest.raises(NombreSucursalDuplicado):
        await CrearSucursalUseCase(repo).ejecutar(CrearSucursalInput(
            nombre="  central ", direccion="x", telefono="y",
        ))


async def test_crear_padre_inexistente():
    repo = _Repo()
    with pytest.raises(SucursalPadreNoEncontrada):
        await CrearSucursalUseCase(repo).ejecutar(CrearSucursalInput(
            nombre="Hija", direccion="x", telefono="y",
            sucursal_padre_id=uuid.uuid4(),
        ))


async def test_actualizar_padre_a_si_misma():
    s = _suc()
    repo = _Repo([s])
    with pytest.raises(JerarquiaSucursalInvalida):
        await ActualizarSucursalUseCase(repo).ejecutar(ActualizarSucursalInput(
            sucursal_id=s.id, sucursal_padre_id=s.id, cambiar_padre=True,
        ))


async def test_actualizar_padre_genera_ciclo():
    abuela = _suc(nombre="Abuela")
    madre = _suc(nombre="Madre", padre_id=abuela.id)
    abuela.sucursal_padre_id = None
    repo = _Repo([abuela, madre])
    # poner a `abuela` como hija de `madre` cierra el ciclo abuela->madre->abuela
    with pytest.raises(JerarquiaSucursalInvalida):
        await ActualizarSucursalUseCase(repo).ejecutar(ActualizarSucursalInput(
            sucursal_id=abuela.id, sucursal_padre_id=madre.id, cambiar_padre=True,
        ))


async def test_desactivar_con_usuarios_activos():
    s = _suc()
    repo = _Repo([s], con_usuarios=True)
    with pytest.raises(SucursalConUsuariosActivos):
        await DesactivarSucursalUseCase(repo).ejecutar(s.id)


async def test_desactivar_ok():
    s = _suc()
    repo = _Repo([s], con_usuarios=False)
    res = await DesactivarSucursalUseCase(repo).ejecutar(s.id)
    assert res.activo is False


async def test_obtener_inexistente():
    with pytest.raises(SucursalNoEncontrada):
        await DesactivarSucursalUseCase(_Repo()).ejecutar(uuid.uuid4())
