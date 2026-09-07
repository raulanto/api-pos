"""Motor de promociones (`domain.services.evaluar`): puro, sin fakes de repo."""
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.modules.promociones.domain.entities import (
    Promocion, PromocionObjetivo, TipoPromocion,
)
from app.modules.promociones.domain.services import LineaEval, evaluar

AHORA = datetime(2026, 9, 7, 12, 0, tzinfo=timezone.utc)
SUC = uuid.uuid4()
PROD = uuid.uuid4()
PRES = uuid.uuid4()


def _obj(producto_id=None, producto_unidad_id=None) -> PromocionObjetivo:
    return PromocionObjetivo(
        id=uuid.uuid4(), promocion_id=uuid.uuid4(),
        producto_id=producto_id, producto_unidad_id=producto_unidad_id,
    )


def _promo(tipo, **kw) -> Promocion:
    kw.setdefault("nombre", "P")
    kw.setdefault("objetivos", [_obj(producto_id=PROD)])
    return Promocion.crear(tipo=tipo, **kw)


def _linea(indice, cantidad, precio, producto_id=PROD, producto_unidad_id=None) -> LineaEval:
    return LineaEval(
        indice=indice, producto_id=producto_id, producto_unidad_id=producto_unidad_id,
        cantidad=Decimal(str(cantidad)), precio_unitario=Decimal(str(precio)),
    )


def test_porcentaje():
    promo = _promo(TipoPromocion.PORCENTAJE, descuento_pct=Decimal("10"))
    [r] = evaluar([promo], [_linea(0, 3, "100")], AHORA, SUC)
    assert r.promo_id == promo.id
    assert r.promo_descuento == Decimal("30.00")   # 3 * 100 * 10%


def test_precio_fijo_con_cantidad_minima_mayoreo_presentacion():
    promo = _promo(
        TipoPromocion.PRECIO_FIJO, precio_fijo=Decimal("12"),
        cantidad_minima=Decimal("5"), objetivos=[_obj(producto_unidad_id=PRES)],
    )
    linea = lambda q: _linea(0, q, "20", producto_unidad_id=PRES)  # noqa: E731
    [bajo] = evaluar([promo], [linea(4)], AHORA, SUC)
    assert bajo.promo_descuento == Decimal("0")
    [alto] = evaluar([promo], [linea(5)], AHORA, SUC)
    assert alto.promo_descuento == Decimal("40.00")   # 5 * (20 - 12)


def test_nxm_2x1_una_linea():
    promo = _promo(TipoPromocion.NXM, nxm_lleva=2, nxm_paga=1)
    [r] = evaluar([promo], [_linea(0, 4, "25")], AHORA, SUC)
    assert r.promo_descuento == Decimal("50.00")   # 2 unidades gratis a 25


def test_nxm_3x2_cruza_lineas_regala_la_mas_barata():
    promo = _promo(TipoPromocion.NXM, nxm_lleva=3, nxm_paga=2)
    lineas = [_linea(0, 3, "30"), _linea(1, 3, "10")]   # 6 uds -> 2 grupos -> 2 libres
    r0, r1 = evaluar([promo], lineas, AHORA, SUC)
    assert r1.promo_descuento == Decimal("20.00")   # 2 uds libres de la línea barata
    assert r0.promo_descuento == Decimal("0")


def test_prioridad_gana_la_menor():
    barata = _promo(TipoPromocion.PORCENTAJE, nombre="A", descuento_pct=Decimal("50"), prioridad=1)
    cara = _promo(TipoPromocion.PORCENTAJE, nombre="B", descuento_pct=Decimal("10"), prioridad=9)
    [r] = evaluar([cara, barata], [_linea(0, 1, "100")], AHORA, SUC)
    assert r.promo_id == barata.id
    assert r.promo_descuento == Decimal("50.00")


def test_fuera_de_vigencia_no_aplica():
    promo = _promo(
        TipoPromocion.PORCENTAJE, descuento_pct=Decimal("10"),
        vigente_hasta=AHORA - timedelta(days=1),
    )
    [r] = evaluar([promo], [_linea(0, 1, "100")], AHORA, SUC)
    assert r.promo_descuento == Decimal("0")


def test_otra_sucursal_no_aplica():
    promo = _promo(
        TipoPromocion.PORCENTAJE, descuento_pct=Decimal("10"), sucursal_id=uuid.uuid4(),
    )
    [r] = evaluar([promo], [_linea(0, 1, "100")], AHORA, SUC)
    assert r.promo_descuento == Decimal("0")
