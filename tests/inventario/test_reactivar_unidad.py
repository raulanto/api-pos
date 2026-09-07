"""Reactivar una presentación (producto_unidad) dada de baja."""
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.modules.inventario.domain.entities import ProductoUnidad
from app.modules.inventario.domain.exceptions import (
    UnidadNoEncontrada, UnidadDuplicada, CodigoBarrasUnidadDuplicado,
)
from app.modules.inventario.application.use_cases.gestionar_unidades import (
    ReactivarUnidadUseCase,
)

PROD = uuid.uuid4()


def _u(nombre="Reja x24", codigo=None, activo=False, pid=PROD) -> ProductoUnidad:
    return ProductoUnidad(
        id=uuid.uuid4(), producto_id=pid, nombre=nombre, unidad_medida="reja",
        factor=Decimal("24"), precio_venta=Decimal("380"), codigo_barras=codigo,
        activo=activo, created_at=datetime.now(timezone.utc),
    )


class _UnidadRepo:
    def __init__(self, unidad, nombre_ocupado=False, codigo_ocupado=False):
        self._u = unidad
        self._nombre_ocupado = nombre_ocupado
        self._codigo_ocupado = codigo_ocupado
        self.actualizada = None

    async def obtener(self, uid):
        return self._u if self._u and self._u.id == uid else None

    async def existe_nombre(self, producto_id, nombre):
        return self._nombre_ocupado

    async def obtener_por_codigo_barras(self, codigo_barras):
        return _u(nombre="Otra", activo=True) if self._codigo_ocupado else None

    async def actualizar(self, unidad):
        self.actualizada = unidad


class _ProdRepo:
    async def buscar_por_codigo_barras(self, cb):
        return None


async def test_reactiva_ok():
    u = _u(activo=False)
    repo = _UnidadRepo(u)
    out = await ReactivarUnidadUseCase(repo, _ProdRepo()).ejecutar(PROD, u.id)
    assert out.activo is True
    assert repo.actualizada is u


async def test_ya_activa_es_idempotente():
    u = _u(activo=True)
    repo = _UnidadRepo(u)
    out = await ReactivarUnidadUseCase(repo, _ProdRepo()).ejecutar(PROD, u.id)
    assert out.activo is True
    assert repo.actualizada is None          # no reescribe


async def test_inexistente_o_de_otro_producto():
    u = _u(activo=False)
    with pytest.raises(UnidadNoEncontrada):
        await ReactivarUnidadUseCase(_UnidadRepo(u), _ProdRepo()).ejecutar(uuid.uuid4(), u.id)


async def test_nombre_ya_ocupado_por_otra_activa():
    u = _u(activo=False)
    repo = _UnidadRepo(u, nombre_ocupado=True)
    with pytest.raises(UnidadDuplicada):
        await ReactivarUnidadUseCase(repo, _ProdRepo()).ejecutar(PROD, u.id)


async def test_codigo_barras_ya_ocupado():
    u = _u(codigo="750123", activo=False)
    repo = _UnidadRepo(u, codigo_ocupado=True)
    with pytest.raises(CodigoBarrasUnidadDuplicado):
        await ReactivarUnidadUseCase(repo, _ProdRepo()).ejecutar(PROD, u.id)
