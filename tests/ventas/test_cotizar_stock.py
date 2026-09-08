"""`cotizar` informa disponibilidad por línea sin bloquear ni fallar."""
import uuid
from decimal import Decimal

from app.modules.ventas.domain.entities import CajaTurno, ESTADO_TURNO_ABIERTO
from app.modules.ventas.application.use_cases.crear_venta import (
    CrearVentaUseCase, CotizarVentaInput, LineaInput,
)

SUC = uuid.uuid4()
PROD = uuid.uuid4()


class _CajaRepo:
    async def obtener_por_id(self, tid):
        from datetime import datetime, timezone
        return CajaTurno(id=tid, sucursal_id=SUC, usuario_id=uuid.uuid4(),
                         saldo_inicial=Decimal("0"), estado=ESTADO_TURNO_ABIERTO,
                         abierto_en=datetime.now(timezone.utc))


class _Inv:
    def __init__(self, disp):
        self._disp = disp

    async def precio_mayoreo_aplicable(self, pid, cant):
        return None

    async def convertir_a_base(self, producto_id, cantidad, producto_unidad_id=None):
        return cantidad

    async def stock_disponible(self, producto_id, sucursal_id, producto_unidad_id=None):
        return self._disp


class _Promos:
    async def evaluar(self, sucursal_id, lineas, **kw):
        return []


def _uc(disp):
    return CrearVentaUseCase(None, _CajaRepo(), _Inv(disp), None, None, promociones=_Promos())


def _in(cantidad):
    return CotizarVentaInput(
        sucursal_id=SUC, descuento_total=Decimal("0"),
        lineas=[LineaInput(producto_id=PROD, cantidad=Decimal(cantidad),
                           precio_unitario=Decimal("10"))],
    )


async def test_hay_stock_true_si_alcanza():
    cot = await _uc(Decimal("10")).cotizar(_in("3"))
    assert cot.lineas[0].stock_disponible == Decimal("10")
    assert cot.lineas[0].hay_stock is True


async def test_hay_stock_false_si_falta():
    cot = await _uc(Decimal("2")).cotizar(_in("3"))
    assert cot.lineas[0].hay_stock is False


async def test_stock_none_es_ilimitado():
    cot = await _uc(None).cotizar(_in("9999"))
    assert cot.lineas[0].stock_disponible is None
    assert cot.lineas[0].hay_stock is True
