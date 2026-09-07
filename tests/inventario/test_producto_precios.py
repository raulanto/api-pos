"""Mayoreo, precio con IVA incluido y sobre pedido en la entidad Producto."""
import uuid
from decimal import Decimal

import pytest

from app.modules.inventario.domain.entities import Producto
from app.modules.inventario.application.use_cases.crear_producto import _validar_mayoreo


def _p(**kw):
    base = dict(
        sku="X", nombre="P", categoria_id=uuid.uuid4(), unidad_medida="pz",
        precio_venta=Decimal("100"), costo=Decimal("60"), impuesto_tasa=Decimal("16"),
    )
    base.update(kw)
    return Producto.crear(**base)


def test_precio_menudeo_sin_mayoreo():
    assert _p().precio_para_cantidad(Decimal("999")) == Decimal("100")


def test_precio_mayoreo_al_alcanzar_el_minimo():
    p = _p(precio_mayoreo=Decimal("80"), cantidad_minima_mayoreo=Decimal("12"))
    assert p.precio_para_cantidad(Decimal("11")) == Decimal("100")   # menudeo
    assert p.precio_para_cantidad(Decimal("12")) == Decimal("80")    # mayoreo
    assert p.precio_para_cantidad(Decimal("50")) == Decimal("80")


def test_permite_venta_sin_stock():
    assert _p().permite_venta_sin_stock is False
    assert _p(permite_stock_negativo=True).permite_venta_sin_stock is True
    assert _p(es_sobre_pedido=True).permite_venta_sin_stock is True


def test_validar_mayoreo():
    _validar_mayoreo(None, None)                                  # ok: ninguno
    _validar_mayoreo(Decimal("80"), Decimal("12"))               # ok: par completo
    with pytest.raises(ValueError):
        _validar_mayoreo(Decimal("80"), None)                    # falta la cantidad
    with pytest.raises(ValueError):
        _validar_mayoreo(None, Decimal("12"))                    # falta el precio
    with pytest.raises(ValueError):
        _validar_mayoreo(Decimal("80"), Decimal("0"))            # cantidad <= 0
    with pytest.raises(ValueError):
        _validar_mayoreo(Decimal("-1"), Decimal("12"))           # precio negativo
