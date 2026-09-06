"""Tests de `EliminarProductoUseCase` (borrado físico de producto).

Dobles en memoria: no toca BD ni S3. Verifica los guardas (historial de
movimientos, componente de kit, IntegrityError por ventas) y la limpieza de S3.
"""
import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from app.modules.inventario.application.use_cases.gestionar_productos import (
    EliminarProductoUseCase,
)
from app.modules.inventario.domain.exceptions import (
    ProductoNoEncontrado, ProductoConHistorial, ProductoEsComponenteDeKit,
)


class _ProdRepo:
    def __init__(self, existe=True, keys=None, revienta=False):
        self._existe = existe
        self._keys = keys or []
        self._revienta = revienta
        self.eliminado = None

    async def obtener_por_id(self, pid, includes=frozenset()):
        return object() if self._existe else None

    async def eliminar_fisico(self, pid):
        if self._revienta:
            raise IntegrityError("DELETE", {}, Exception("FK detalle_venta"))
        self.eliminado = pid
        return list(self._keys)


class _MovRepo:
    def __init__(self, con_movimientos=False):
        self._con = con_movimientos

    async def existe_para_producto(self, pid):
        return self._con


class _CompRepo:
    def __init__(self, es_componente=False):
        self._es = es_componente

    async def es_componente_de_kit_activo(self, pid):
        return self._es


class _Almacen:
    def __init__(self):
        self.borradas = []

    @staticmethod
    def key_miniatura(key):
        return key.replace("originales/", "thumbnails/")

    async def eliminar(self, key):
        self.borradas.append(key)


def _uc(prod=None, mov=None, comp=None, alm=None):
    return EliminarProductoUseCase(
        prod or _ProdRepo(), mov or _MovRepo(), comp or _CompRepo(), alm,
    )


async def test_producto_inexistente():
    with pytest.raises(ProductoNoEncontrado):
        await _uc(prod=_ProdRepo(existe=False)).ejecutar(uuid.uuid4())


async def test_con_movimientos_rechaza_y_no_borra():
    prod = _ProdRepo()
    with pytest.raises(ProductoConHistorial):
        await _uc(prod=prod, mov=_MovRepo(con_movimientos=True)).ejecutar(uuid.uuid4())
    assert prod.eliminado is None


async def test_componente_de_kit_activo_rechaza():
    with pytest.raises(ProductoEsComponenteDeKit):
        await _uc(comp=_CompRepo(es_componente=True)).ejecutar(uuid.uuid4())


async def test_integrityerror_se_traduce_a_conflicto():
    with pytest.raises(ProductoConHistorial):
        await _uc(prod=_ProdRepo(revienta=True)).ejecutar(uuid.uuid4())


async def test_happy_path_borra_y_limpia_s3():
    pid = uuid.uuid4()
    key = "originales/producto/abc/deadbeef.png"
    prod = _ProdRepo(keys=[key])
    alm = _Almacen()
    await _uc(prod=prod, alm=alm).ejecutar(pid)
    assert prod.eliminado == pid
    assert alm.borradas == [key, "thumbnails/producto/abc/deadbeef.png"]


async def test_sin_almacen_no_falla():
    await _uc(prod=_ProdRepo(keys=["originales/x/y.png"])).ejecutar(uuid.uuid4())
