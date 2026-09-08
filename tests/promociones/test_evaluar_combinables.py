"""Motor de promociones: apilado combinable, tope_descuento, monto_minimo_compra."""
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from app.modules.promociones.domain.entities import (
    Promocion, PromocionObjetivo, TipoPromocion,
)
from app.modules.promociones.domain.services import LineaEval, evaluar
from app.modules.promociones.domain.value_objects import ContextoEvaluacion

AHORA = datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc)
SUC = uuid.uuid4()
PROD = uuid.uuid4()


def _promo(nombre, tipo, *, prioridad=100, combinable=False, tope_descuento=None,
           monto_minimo_compra=None, **kw) -> Promocion:
    return Promocion.crear(
        nombre=nombre, tipo=tipo, prioridad=prioridad, combinable=combinable,
        tope_descuento=tope_descuento, monto_minimo_compra=monto_minimo_compra,
        objetivos=[PromocionObjetivo(id=uuid.uuid4(), promocion_id=uuid.uuid4(),
                                     producto_id=PROD)],
        **kw,
    )


def _ev(promos, cantidad="1", precio="100"):
    linea = LineaEval(indice=0, producto_id=PROD, producto_unidad_id=None,
                      cantidad=Decimal(cantidad), precio_unitario=Decimal(precio))
    ctx = ContextoEvaluacion(
        momento=AHORA, sucursal_id=SUC,
        total_bruto=Decimal(cantidad) * Decimal(precio),
    )
    return evaluar(promos, [linea], ctx)[0]


def test_exclusiva_gana_y_cierra_la_linea():
    excl = _promo("E", TipoPromocion.PORCENTAJE, descuento_pct=Decimal("20"), prioridad=1)
    comb = _promo("C", TipoPromocion.PORCENTAJE, descuento_pct=Decimal("50"),
                  prioridad=2, combinable=True)
    r = _ev([comb, excl])
    assert r.promo_descuento == Decimal("20.00")          # sólo la exclusiva
    assert [a.etiqueta for a in r.desglose] == ["E"]


def test_dos_combinables_apilan_sobre_residual():
    c1 = _promo("C1", TipoPromocion.PORCENTAJE, descuento_pct=Decimal("10"),
                prioridad=1, combinable=True)
    c2 = _promo("C2", TipoPromocion.PORCENTAJE, descuento_pct=Decimal("50"),
                prioridad=2, combinable=True)
    r = _ev([c1, c2], precio="100")
    # 10% de 100 = 10 -> residual 90 ; 50% de 90 = 45 -> total 55
    assert r.promo_descuento == Decimal("55.00")
    assert sorted(a.etiqueta for a in r.desglose) == ["C1", "C2"]
    assert sum(a.monto for a in r.desglose) == Decimal("55.00")


def test_tope_descuento_corta():
    comb = _promo("C", TipoPromocion.PORCENTAJE, descuento_pct=Decimal("50"),
                  combinable=True, tope_descuento=Decimal("30"))
    r = _ev([comb], precio="100")
    assert r.promo_descuento == Decimal("30.00")          # 50 topado a 30


def test_monto_minimo_compra_excluye():
    promo = _promo("M", TipoPromocion.PORCENTAJE, descuento_pct=Decimal("10"),
                   monto_minimo_compra=Decimal("500"))
    assert _ev([promo], precio="100").promo_descuento == Decimal("0")     # 100 < 500
    assert _ev([promo], cantidad="6", precio="100").promo_descuento == Decimal("60.00")
