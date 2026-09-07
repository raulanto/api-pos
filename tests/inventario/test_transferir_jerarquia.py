"""Fase 3: la transferencia entre sucursales valida la jerarquía padre/hermana."""
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.modules.sucursales.domain.entities import Sucursal, TipoSucursal
from app.modules.inventario.domain.exceptions import TransferenciaInvalida
from app.modules.inventario.application.use_cases.transferir_stock import (
    TransferirStockUseCase, TransferirStockInput,
)


def _suc(padre_id=None) -> Sucursal:
    return Sucursal(
        id=uuid.uuid4(), nombre="S", direccion="x", telefono="y",
        activo=True, created_at=datetime.now(timezone.utc),
        tipo=TipoSucursal.TIENDA, sucursal_padre_id=padre_id,
    )


class _SucRepo:
    def __init__(self, sucursales):
        self._por_id = {s.id: s for s in sucursales}

    async def obtener_por_id(self, sid):
        return self._por_id.get(sid)


class _ProdRepo:
    async def obtener_por_id(self, pid):
        return type("P", (), {
            "nombre": "P", "requiere_lote": False,
            "permite_stock_negativo": True, "permite_venta_sin_stock": True,
        })()


class _ExistRepo:
    async def obtener(self, pid, sid):
        return None

    async def crear(self, e):
        pass

    async def actualizar_cantidad(self, pid, sid, q):
        pass


class _MovRepo:
    async def guardar(self, m):
        pass


def _uc(suc_repo):
    return TransferirStockUseCase(
        _ProdRepo(), _ExistRepo(), _MovRepo(), None, suc_repo,
    )


def _input(origen, destino):
    return TransferirStockInput(
        producto_id=uuid.uuid4(),
        sucursal_origen_id=origen, sucursal_destino_id=destino,
        cantidad=Decimal("1"), usuario_id=uuid.uuid4(),
    )


async def test_padre_hijo_ok():
    padre = _suc()
    hija = _suc(padre_id=padre.id)
    await _uc(_SucRepo([padre, hija])).ejecutar(_input(padre.id, hija.id))
    await _uc(_SucRepo([padre, hija])).ejecutar(_input(hija.id, padre.id))


async def test_hermanas_ok():
    padre = _suc()
    a = _suc(padre_id=padre.id)
    b = _suc(padre_id=padre.id)
    await _uc(_SucRepo([padre, a, b])).ejecutar(_input(a.id, b.id))


async def test_no_relacionadas_rechaza():
    a = _suc()
    b = _suc()
    with pytest.raises(TransferenciaInvalida):
        await _uc(_SucRepo([a, b])).ejecutar(_input(a.id, b.id))


async def test_primas_rechaza():
    raiz = _suc()
    m1 = _suc(padre_id=raiz.id)
    m2 = _suc(padre_id=raiz.id)
    prima1 = _suc(padre_id=m1.id)
    prima2 = _suc(padre_id=m2.id)
    with pytest.raises(TransferenciaInvalida):
        await _uc(_SucRepo([raiz, m1, m2, prima1, prima2])).ejecutar(
            _input(prima1.id, prima2.id)
        )


async def test_sin_sucursal_repo_no_valida():
    a, b = uuid.uuid4(), uuid.uuid4()
    await _uc(None).ejecutar(_input(a, b))
