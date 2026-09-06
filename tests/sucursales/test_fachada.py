"""Tests de subir/eliminar la imagen de fachada de una sucursal.

El `fachada_storage` se stubea (no toca S3 real)."""
import uuid
from datetime import datetime, timezone

import pytest

from app.modules.sucursales.domain.entities import Sucursal, TipoSucursal
from app.modules.sucursales.domain.exceptions import SucursalNoEncontrada
from app.modules.sucursales.application.use_cases import gestionar_fachada as gf
from app.modules.sucursales.application.use_cases.gestionar_fachada import (
    SubirFachadaUseCase, SubirFachadaInput, EliminarFachadaUseCase,
)


def _suc(key=None) -> Sucursal:
    return Sucursal(
        id=uuid.uuid4(), nombre="Tienda", direccion="x", telefono="y",
        activo=True, created_at=datetime.now(timezone.utc),
        tipo=TipoSucursal.TIENDA, imagen_fachada_key=key,
    )


class _Repo:
    def __init__(self, sucursal):
        self._s = sucursal
        self.actualizadas = []
        self.revienta = False

    async def obtener_por_id(self, sid):
        return self._s

    async def actualizar(self, s):
        if self.revienta:
            raise RuntimeError("db down")
        self.actualizadas.append(s)


class _FakeStorage:
    EXTENSIONES_PERMITIDAS = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}

    def __init__(self):
        self.subidas = []
        self.borradas = []

    def content_type_valido(self, ct):
        return ct in self.EXTENSIONES_PERMITIDAS

    def nueva_key(self, sucursal_id, content_type):
        return f"sucursales/{sucursal_id}/deadbeef{self.EXTENSIONES_PERMITIDAS[content_type]}"

    async def subir(self, key, contenido, content_type):
        self.subidas.append(key)

    async def eliminar(self, key):
        self.borradas.append(key)

    def url_publica(self, key):
        return "http://s3.test/" + key


@pytest.fixture
def storage(monkeypatch):
    fake = _FakeStorage()
    monkeypatch.setattr(gf, "fachada_storage", fake)
    return fake


async def test_subir_ok_guarda_key(storage):
    s = _suc()
    repo = _Repo(s)
    res = await SubirFachadaUseCase(repo).ejecutar(SubirFachadaInput(
        sucursal_id=s.id, contenido=b"jpegbytes", content_type="image/jpeg",
    ))
    assert res.imagen_fachada_key == storage.subidas[0]
    assert res.imagen_fachada_url == "http://s3.test/" + res.imagen_fachada_key
    assert repo.actualizadas == [res]


async def test_subir_reemplaza_y_borra_la_anterior(storage):
    s = _suc(key="sucursales/x/vieja.png")
    res = await SubirFachadaUseCase(_Repo(s)).ejecutar(SubirFachadaInput(
        sucursal_id=s.id, contenido=b"x", content_type="image/png",
    ))
    assert "sucursales/x/vieja.png" in storage.borradas
    assert res.imagen_fachada_key != "sucursales/x/vieja.png"


async def test_subir_content_type_no_permitido(storage):
    s = _suc()
    with pytest.raises(ValueError):
        await SubirFachadaUseCase(_Repo(s)).ejecutar(SubirFachadaInput(
            sucursal_id=s.id, contenido=b"x", content_type="application/pdf",
        ))
    assert storage.subidas == []


async def test_subir_sucursal_inexistente(storage):
    class _RepoNone:
        async def obtener_por_id(self, sid):
            return None
    with pytest.raises(SucursalNoEncontrada):
        await SubirFachadaUseCase(_RepoNone()).ejecutar(SubirFachadaInput(
            sucursal_id=uuid.uuid4(), contenido=b"x", content_type="image/jpeg",
        ))


async def test_subir_compensa_si_falla_el_guardado(storage):
    s = _suc()
    repo = _Repo(s)
    repo.revienta = True
    with pytest.raises(RuntimeError):
        await SubirFachadaUseCase(repo).ejecutar(SubirFachadaInput(
            sucursal_id=s.id, contenido=b"x", content_type="image/webp",
        ))
    assert storage.borradas == storage.subidas and storage.borradas


async def test_eliminar_fachada(storage):
    s = _suc(key="sucursales/x/f.jpg")
    res = await EliminarFachadaUseCase(_Repo(s)).ejecutar(s.id)
    assert res.imagen_fachada_key is None
    assert "sucursales/x/f.jpg" in storage.borradas
