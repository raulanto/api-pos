"""Desglose del saldo (unidad base) a cada presentación."""
import uuid
from decimal import Decimal

import pytest

from app.modules.inventario.domain.exceptions import ProductoNoEncontrado
from app.modules.inventario.application.use_cases.consultar_existencias import (
    DesglosarStockUseCase,
)

PID = uuid.uuid4()
S1, S2 = uuid.uuid4(), uuid.uuid4()


class _ProdRepo:
    def __init__(self, existe=True): self._e = existe
    async def obtener_por_id(self, pid, includes=frozenset()):
        if not self._e:
            return None
        return type("P", (), {"id": pid, "unidad_medida": "reja"})()


class _UnidadRepo:
    def __init__(self, unidades): self._u = unidades
    async def listar_por_producto(self, pid, incluir_inactivas=False): return self._u


class _ExistRepo:
    def __init__(self, filas): self._f = filas
    async def listar(self, producto_id=None, sucursal_id=None): return self._f


def _e(sid, cant):
    return type("E", (), {
        "sucursal_id": sid, "cantidad": Decimal(cant),
        "stock_minimo": Decimal("1"), "stock_maximo": Decimal("10"),
    })()


def _pu(nombre, factor):
    return type("U", (), {"id": uuid.uuid4(), "nombre": nombre, "factor": Decimal(factor)})()


async def test_reja_de_8_desglosa_a_botellas():
    # 8.8750 rejas -> 71 botellas (factor 1/8), y 213 (factor 1/24)
    uc = DesglosarStockUseCase(
        _ExistRepo([_e(S1, "8.8750")]), _ProdRepo(),
        _UnidadRepo([_pu("Botella 2L", "0.125"), _pu("Vaso", "0.0416667")]),
    )
    d = await uc.ejecutar(PID)
    assert d.unidad_base == "reja"
    assert d.cantidad_base_global == Decimal("8.8750")
    base = d.presentaciones_global[0]
    assert base.producto_unidad_id is None and base.cantidad_entera == 8
    botella = d.presentaciones_global[1]
    assert botella.cantidad == Decimal("71.0000")
    assert botella.cantidad_entera == 71


async def test_suma_global_entre_sucursales():
    uc = DesglosarStockUseCase(
        _ExistRepo([_e(S1, "5"), _e(S2, "3.5")]), _ProdRepo(),
        _UnidadRepo([_pu("Botella 2L", "0.125")]),
    )
    d = await uc.ejecutar(PID)
    assert d.cantidad_base_global == Decimal("8.5")
    assert len(d.por_sucursal) == 2
    assert d.presentaciones_global[1].cantidad == Decimal("68.0000")   # 8.5 / 0.125


async def test_filtra_por_sucursal():
    uc = DesglosarStockUseCase(
        _ExistRepo([_e(S1, "5"), _e(S2, "3")]), _ProdRepo(), _UnidadRepo([]),
    )
    d = await uc.ejecutar(PID, sucursal_ids=[S1])
    assert [s.sucursal_id for s in d.por_sucursal] == [S1]
    assert d.cantidad_base_global == Decimal("5")


async def test_producto_inexistente():
    uc = DesglosarStockUseCase(_ExistRepo([]), _ProdRepo(existe=False), _UnidadRepo([]))
    with pytest.raises(ProductoNoEncontrado):
        await uc.ejecutar(PID)
