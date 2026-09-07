"""Vender una PRESENTACIÓN cuyo `factor < 1` (sub-unidad de la unidad base).

Ej: base = "reja" (0 decimales, no fraccionable), presentación "botella" con
factor 1/8. Vender 1 botella = 0.125 rejas: no debe fallar con CantidadNoVendible
ni redondearse a 0. La SALIDA que viene de una presentación se identifica por
`unidad_capturada_id`.
"""
import uuid
from decimal import Decimal

import pytest

from app.modules.inventario.domain.entities import Producto
from app.modules.inventario.domain.value_objects import TipoMovimiento, TipoProducto
from app.modules.inventario.domain.exceptions import CantidadNoVendible
from app.modules.inventario.application.use_cases.aplicar_movimiento import (
    AplicarMovimientoUseCase, AplicarMovimientoInput,
)

PID, SID, UID = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()


def _producto():
    p = Producto.crear(
        sku="CLO-001", nombre="Coca Cola", categoria_id=uuid.uuid4(),
        unidad_medida="reja", precio_venta=Decimal("200"), costo=Decimal("168"),
        impuesto_tasa=Decimal("0"), tipo=TipoProducto.SIMPLE,
        unidad_medida_id=uuid.uuid4(),
    )
    p.id = PID
    return p


class _ProdRepo:
    def __init__(self, p): self._p = p
    async def obtener_por_id(self, pid): return self._p
    async def actualizar(self, p): pass


class _UMRepo:
    async def obtener(self, umid):
        return type("U", (), {"decimales": 0})()   # "reja": piezas enteras


class _ExistRepo:
    def __init__(self, cant): self.cant = Decimal(cant); self.nuevo = None
    async def obtener(self, pid, sid, para_actualizar=False):
        return type("E", (), {"cantidad": self.cant})()
    async def actualizar_cantidad(self, pid, sid, q): self.nuevo = q
    async def crear(self, e): pass


class _MovRepo:
    def __init__(self): self.movs = []
    async def guardar(self, m): self.movs.append(m)


def _uc(exist):
    return AplicarMovimientoUseCase(
        _ProdRepo(_producto()), exist, _MovRepo(),
        event_port=None, unidad_medida_repo=_UMRepo(),
    )


async def test_venta_de_presentacion_subunidad_ok():
    exist = _ExistRepo("9")
    uc = _uc(exist)
    await uc.ejecutar(AplicarMovimientoInput(
        producto_id=PID, sucursal_id=SID, tipo=TipoMovimiento.SALIDA,
        cantidad=Decimal("0.125"), referencia_tipo="venta", usuario_id=UID,
        unidad_capturada_id=uuid.uuid4(), cantidad_capturada=Decimal("1"),
    ))
    assert exist.nuevo == Decimal("8.8750")
    assert uc._movimiento_repo.movs[0].cantidad == Decimal("0.1250")


async def test_misma_cantidad_sin_presentacion_es_rechazada():
    uc = _uc(_ExistRepo("9"))
    with pytest.raises(CantidadNoVendible):
        await uc.ejecutar(AplicarMovimientoInput(
            producto_id=PID, sucursal_id=SID, tipo=TipoMovimiento.SALIDA,
            cantidad=Decimal("0.125"), referencia_tipo="ajuste", usuario_id=UID,
        ))
