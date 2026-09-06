"""Tests del caso de uso `SubirImagenUseCase`.

Sin BD ni S3 reales: dobles en memoria para repos y almacén. Cubre la validación
(allowlist de content-type, límite de tamaño), el desmarcado de `es_principal` y
la compensación (borra el objeto de S3 si el INSERT falla).
"""
import uuid

import pytest

from app.modules.inventario.application.use_cases.subir_imagen import (
    SubirImagenUseCase, SubirImagenInput,
)
from app.modules.inventario.domain.exceptions import ImagenInvalida, ProductoNoEncontrado


class _ProdRepo:
    def __init__(self, existe=True):
        self._existe = existe

    async def obtener_por_id(self, _pid):
        return object() if self._existe else None


class _UnidadRepo:
    async def obtener(self, _uid):
        return object()


class _ImagenRepo:
    def __init__(self):
        self.creadas = []
        self.desmarcadas = []

    async def desmarcar_principal(self, producto_id, producto_unidad_id, excepto_id=None):
        self.desmarcadas.append((producto_id, producto_unidad_id))

    async def crear(self, imagen):
        self.creadas.append(imagen)


class _Almacen:
    def __init__(self):
        self.subidas = []
        self.borradas = []

    def nueva_key(self, *, dueno, dueno_id, content_type):
        return f"originales/{dueno}/{dueno_id}/deadbeef.png"

    @staticmethod
    def key_miniatura(key):
        return key.replace("originales/", "thumbnails/")

    async def subir(self, contenido, content_type, key):
        self.subidas.append(key)

    async def eliminar(self, key):
        self.borradas.append(key)

    def url_publica(self, key, *, expira=None):
        return "http://s3.test/" + key


def _uc(imagen_repo=None, almacen=None, producto_existe=True):
    return SubirImagenUseCase(
        imagen_repo or _ImagenRepo(),
        _ProdRepo(producto_existe),
        _UnidadRepo(),
        almacen or _Almacen(),
    )


async def test_sube_y_persiste_object_key():
    pid = uuid.uuid4()
    repo, alm = _ImagenRepo(), _Almacen()
    img = await _uc(repo, alm).ejecutar(SubirImagenInput(
        contenido=b"binario", content_type="image/png",
        producto_id=pid, es_principal=True,
    ))
    assert img.object_key == alm.subidas[0]
    assert img.content_type == "image/png"
    # El 201 ya trae url/thumbnail_url prefirmadas (igual que una lectura).
    assert img.url == "http://s3.test/" + img.object_key
    assert img.thumbnail_url == "http://s3.test/" + img.object_key.replace(
        "originales/", "thumbnails/"
    )
    assert repo.creadas == [img]
    assert repo.desmarcadas == [(pid, None)]


async def test_rechaza_content_type_no_permitido():
    with pytest.raises(ImagenInvalida):
        await _uc().ejecutar(SubirImagenInput(
            contenido=b"x", content_type="application/pdf", producto_id=uuid.uuid4(),
        ))


async def test_rechaza_archivo_demasiado_grande():
    with pytest.raises(ImagenInvalida):
        await _uc().ejecutar(SubirImagenInput(
            contenido=b"x" * (5 * 1024 * 1024 + 1), content_type="image/jpeg",
            producto_id=uuid.uuid4(),
        ))


async def test_dueno_inexistente_no_sube_nada():
    alm = _Almacen()
    with pytest.raises(ProductoNoEncontrado):
        await _uc(almacen=alm, producto_existe=False).ejecutar(SubirImagenInput(
            contenido=b"x", content_type="image/png", producto_id=uuid.uuid4(),
        ))
    assert alm.subidas == []


async def test_compensa_borrando_de_s3_si_falla_el_insert():
    class _RepoBoom(_ImagenRepo):
        async def crear(self, imagen):
            raise RuntimeError("db caída")

    alm = _Almacen()
    with pytest.raises(RuntimeError):
        await _uc(_RepoBoom(), alm).ejecutar(SubirImagenInput(
            contenido=b"x", content_type="image/webp", producto_id=uuid.uuid4(),
        ))
    assert alm.borradas == alm.subidas and alm.borradas
