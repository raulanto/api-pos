"""Condiciones de promo: objetivo por categoría, método de pago, segmento, cupón."""
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from app.modules.promociones.domain.entities import (
    Promocion, PromocionObjetivo, TipoPromocion,
)
from app.modules.promociones.domain.services import LineaEval, evaluar
from app.modules.promociones.domain.value_objects import ContextoEvaluacion

SUC = uuid.uuid4()
PROD = uuid.uuid4()
CAT = uuid.uuid4()
AHORA = datetime(2026, 9, 8, 18, 0, tzinfo=timezone.utc)


def _promo(objetivo, **kw):
    return Promocion.crear(
        nombre="C", tipo=TipoPromocion.PORCENTAJE, descuento_pct=Decimal("10"),
        objetivos=[objetivo], **kw,
    )


def _linea(**kw):
    base = dict(indice=0, producto_id=PROD, producto_unidad_id=None,
               cantidad=Decimal("1"), precio_unitario=Decimal("100"))
    base.update(kw)
    return LineaEval(**base)


def _ev(promo, linea, **ctxkw):
    ctx = ContextoEvaluacion(
        momento=AHORA, sucursal_id=SUC, total_bruto=Decimal("100"), **ctxkw,
    )
    return evaluar([promo], [linea], ctx)[0].promo_descuento


def _obj_cat():
    return PromocionObjetivo(id=uuid.uuid4(), promocion_id=uuid.uuid4(), categoria_id=CAT)


def _obj_prod():
    return PromocionObjetivo(id=uuid.uuid4(), promocion_id=uuid.uuid4(), producto_id=PROD)


def test_objetivo_por_categoria():
    promo = _promo(_obj_cat())
    assert _ev(promo, _linea(categoria_id=CAT)) == Decimal("10.00")
    assert _ev(promo, _linea(categoria_id=uuid.uuid4())) == Decimal("0")


def test_metodo_pago_requerido():
    promo = _promo(_obj_prod(), metodo_pago_requerido="transferencia")
    assert _ev(promo, _linea(), metodos_pago=frozenset({"transferencia"})) == Decimal("10.00")
    assert _ev(promo, _linea(), metodos_pago=frozenset({"efectivo"})) == Decimal("0")


def test_cliente_segmento():
    promo = _promo(_obj_prod(), cliente_segmento="vip")
    assert _ev(promo, _linea(), cliente_segmento="vip") == Decimal("10.00")
    assert _ev(promo, _linea(), cliente_segmento=None) == Decimal("0")


def test_requiere_cupon():
    promo = _promo(_obj_prod(), requiere_cupon=True)
    assert _ev(promo, _linea()) == Decimal("0")                       # sin cupón
    assert _ev(promo, _linea(), promos_por_cupon=frozenset({promo.id})) == Decimal("10.00")
