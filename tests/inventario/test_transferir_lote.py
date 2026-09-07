"""Transferencia entre sucursales de un producto con control por lote:
FEFO-out en origen + ENTRADA al mismo lote en destino."""
import uuid
from decimal import Decimal

import pytest

from app.modules.inventario.domain.value_objects import TipoMovimiento
from app.modules.inventario.domain.exceptions import StockInsuficiente
from app.modules.inventario.application.use_cases.transferir_stock import (
    TransferirStockUseCase, TransferirStockInput,
)

ORIGEN, DESTINO = uuid.uuid4(), uuid.uuid4()
L1, L2 = uuid.uuid4(), uuid.uuid4()


class _ProdRepo:
    def __init__(self, neg=False):
        self._neg = neg

    async def obtener_por_id(self, pid):
        return type("P", (), {
            "id": pid, "nombre": "Leche", "requiere_lote": True,
            "permite_stock_negativo": self._neg, "permite_venta_sin_stock": self._neg,
        })()


class _ExistRepo:
    def __init__(self):
        self.saldos = {(ORIGEN,): Decimal("10"), (DESTINO,): Decimal("0")}
        self.updates = []

    async def obtener(self, pid, sid):
        c = self.saldos.get((sid,))
        return type("E", (), {"cantidad": c})() if c is not None else None

    async def actualizar_cantidad(self, pid, sid, q):
        self.updates.append((sid, q))
        self.saldos[(sid,)] = q

    async def crear(self, e):
        self.saldos[(e.sucursal_id,)] = e.cantidad
        self.updates.append((e.sucursal_id, e.cantidad))


class _LoteRepo:
    def __init__(self, fefo):
        self._fefo = fefo           # [(lote_id, disp)]
        self.ajustes = []           # (sucursal, lote, delta)

    async def lotes_fefo(self, pid, sid):
        return list(self._fefo)

    async def obtener(self, lid):
        return type("L", (), {"id": lid, "costo": Decimal("3")})()

    async def ajustar_saldo(self, pid, sid, lid, delta):
        self.ajustes.append((sid, lid, delta))
        return Decimal("0")


class _MovRepo:
    def __init__(self):
        self.movs = []

    async def guardar(self, m):
        self.movs.append(m)


def _uc(prod, exist, lote, mov):
    return TransferirStockUseCase(prod, exist, mov, None, None, lote)


async def test_fefo_reparte_entre_dos_lotes():
    exist, lote, mov = _ExistRepo(), _LoteRepo([(L1, Decimal("3")), (L2, Decimal("9"))]), _MovRepo()
    await _uc(_ProdRepo(), exist, lote, mov).ejecutar(TransferirStockInput(
        producto_id=uuid.uuid4(), sucursal_origen_id=ORIGEN, sucursal_destino_id=DESTINO,
        cantidad=Decimal("5"), usuario_id=uuid.uuid4(),
    ))
    # L1 aporta 3, L2 aporta 2; en cada lote un -qty en origen y +qty en destino
    assert (ORIGEN, L1, Decimal("-3")) in lote.ajustes
    assert (DESTINO, L1, Decimal("3")) in lote.ajustes
    assert (ORIGEN, L2, Decimal("-2")) in lote.ajustes
    assert (DESTINO, L2, Decimal("2")) in lote.ajustes
    # agregado: origen 10->5, destino 0->5
    assert (ORIGEN, Decimal("5")) in exist.updates
    assert (DESTINO, Decimal("5")) in exist.updates
    # 2 lotes -> 4 movimientos TRANSFERENCIA
    assert len(mov.movs) == 4
    assert all(m.tipo is TipoMovimiento.TRANSFERENCIA and m.lote_id in (L1, L2) for m in mov.movs)


async def test_stock_insuficiente_sin_negativo():
    exist, lote, mov = _ExistRepo(), _LoteRepo([(L1, Decimal("2"))]), _MovRepo()
    with pytest.raises(StockInsuficiente):
        await _uc(_ProdRepo(neg=False), exist, lote, mov).ejecutar(TransferirStockInput(
            producto_id=uuid.uuid4(), sucursal_origen_id=ORIGEN, sucursal_destino_id=DESTINO,
            cantidad=Decimal("5"), usuario_id=uuid.uuid4(),
        ))
    assert mov.movs == []


async def test_negativo_lo_absorbe_el_lote_mas_fefo():
    exist, lote, mov = _ExistRepo(), _LoteRepo([(L1, Decimal("2"))]), _MovRepo()
    await _uc(_ProdRepo(neg=True), exist, lote, mov).ejecutar(TransferirStockInput(
        producto_id=uuid.uuid4(), sucursal_origen_id=ORIGEN, sucursal_destino_id=DESTINO,
        cantidad=Decimal("5"), usuario_id=uuid.uuid4(),
    ))
    assert (ORIGEN, L1, Decimal("-5")) in lote.ajustes
    assert (DESTINO, L1, Decimal("5")) in lote.ajustes
