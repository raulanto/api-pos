"""`unidad_capturada_id` es metadata de trazabilidad (ej. "vino de 1 reja"), pero
tiene que pertenecer al MISMO producto del movimiento. Antes sólo había una FK a
nivel de base de datos (cualquier `producto_unidad` existente pasaba, incluso de
otro producto); `AplicarMovimientoUseCase` ahora lo valida cuando recibe
`unidad_repo`.
"""
import uuid
from decimal import Decimal

import pytest

from app.modules.inventario.domain.entities import Producto
from app.modules.inventario.domain.value_objects import TipoMovimiento, TipoProducto
from app.modules.inventario.domain.exceptions import UnidadInvalida
from app.modules.inventario.application.use_cases.aplicar_movimiento import (
    AplicarMovimientoUseCase, AplicarMovimientoInput,
)

PID, OTRO_PID, SID, UID = uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
UNIDAD_PROPIA, UNIDAD_AJENA = uuid.uuid4(), uuid.uuid4()


def _producto():
    p = Producto.crear(
        sku="TOM-001", nombre="Tomate", categoria_id=uuid.uuid4(),
        unidad_medida="kg", precio_venta=Decimal("14"), costo=Decimal("6.70"),
        impuesto_tasa=Decimal("0"), tipo=TipoProducto.FRACCIONABLE,
        unidad_medida_id=uuid.uuid4(),
    )
    p.id = PID
    return p


class _ProdRepo:
    async def obtener_por_id(self, pid): return _producto()
    async def actualizar(self, p): pass


class _UMRepo:
    async def obtener(self, umid):
        return type("U", (), {"decimales": 3})()


class _ExistRepo:
    async def obtener(self, pid, sid, para_actualizar=False):
        return type("E", (), {"cantidad": Decimal("0")})()
    async def actualizar_cantidad(self, pid, sid, q): pass
    async def crear(self, e): pass


class _MovRepo:
    async def guardar(self, m): pass


class _UnidadRepo:
    """`UNIDAD_PROPIA` pertenece a PID; `UNIDAD_AJENA` pertenece a otro producto."""
    async def obtener(self, unidad_id):
        pid = PID if unidad_id == UNIDAD_PROPIA else OTRO_PID
        return type("Unidad", (), {"producto_id": pid})()


def _uc():
    return AplicarMovimientoUseCase(
        _ProdRepo(), _ExistRepo(), _MovRepo(),
        unidad_medida_repo=_UMRepo(), unidad_repo=_UnidadRepo(),
    )


async def test_unidad_capturada_de_otro_producto_es_rechazada():
    with pytest.raises(UnidadInvalida):
        await _uc().ejecutar(AplicarMovimientoInput(
            producto_id=PID, sucursal_id=SID, tipo=TipoMovimiento.ENTRADA,
            cantidad=Decimal("19.400"), referencia_tipo="compra", usuario_id=UID,
            unidad_capturada_id=UNIDAD_AJENA, cantidad_capturada=Decimal("1"),
        ))


async def test_unidad_capturada_del_mismo_producto_pasa():
    await _uc().ejecutar(AplicarMovimientoInput(
        producto_id=PID, sucursal_id=SID, tipo=TipoMovimiento.ENTRADA,
        cantidad=Decimal("19.400"), referencia_tipo="compra", usuario_id=UID,
        unidad_capturada_id=UNIDAD_PROPIA, cantidad_capturada=Decimal("1"),
    ))
