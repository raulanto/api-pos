"""Vigencia fina: días de la semana (bitmask) y ventana horaria en hora local."""
import uuid
from datetime import datetime, time, timezone
from decimal import Decimal

from app.modules.promociones.domain.entities import (
    Promocion, PromocionObjetivo, TipoPromocion,
)
from app.modules.promociones.domain.services import LineaEval, evaluar
from app.modules.promociones.domain.value_objects import ContextoEvaluacion

SUC = uuid.uuid4()
PROD = uuid.uuid4()
# 2026-09-08 18:00 UTC == 12:00 en America/Mexico_City (UTC-6), un MARTES.
MARTES_MEDIODIA = datetime(2026, 9, 8, 18, 0, tzinfo=timezone.utc)
MARTES_23H = datetime(2026, 9, 9, 5, 0, tzinfo=timezone.utc)   # 23:00 local del martes


def _promo(**kw):
    return Promocion.crear(
        nombre="V", tipo=TipoPromocion.PORCENTAJE, descuento_pct=Decimal("10"),
        objetivos=[PromocionObjetivo(id=uuid.uuid4(), promocion_id=uuid.uuid4(),
                                     producto_id=PROD)],
        **kw,
    )


def _aplica(promo, momento) -> bool:
    linea = LineaEval(indice=0, producto_id=PROD, producto_unidad_id=None,
                      cantidad=Decimal("1"), precio_unitario=Decimal("100"))
    ctx = ContextoEvaluacion(momento=momento, sucursal_id=SUC, total_bruto=Decimal("100"))
    return evaluar([promo], [linea], ctx)[0].promo_descuento > 0


def test_dias_semana_bitmask():
    solo_martes = _promo(dias_semana=1 << 1)          # bit 1 = martes
    assert _aplica(solo_martes, MARTES_MEDIODIA)
    solo_miercoles = _promo(dias_semana=1 << 2)
    assert not _aplica(solo_miercoles, MARTES_MEDIODIA)


def test_ventana_horaria_local():
    manana = _promo(hora_desde=time(11, 0), hora_hasta=time(14, 0))
    assert _aplica(manana, MARTES_MEDIODIA)           # 12:00 local dentro
    tarde = _promo(hora_desde=time(13, 0), hora_hasta=time(18, 0))
    assert not _aplica(tarde, MARTES_MEDIODIA)        # 12:00 local fuera


def test_ventana_cruza_medianoche():
    nocturna = _promo(hora_desde=time(22, 0), hora_hasta=time(2, 0))
    assert not _aplica(nocturna, MARTES_MEDIODIA)     # 12:00 local
    assert _aplica(nocturna, MARTES_23H)              # 23:00 local


def test_sin_restriccion_horaria_aplica_siempre():
    assert _aplica(_promo(), MARTES_MEDIODIA)
