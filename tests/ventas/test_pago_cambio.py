"""Pago en efectivo: `monto_recibido` y `cambio`."""
from decimal import Decimal

import pytest

from app.modules.ventas.domain.entities import Pago, Venta, DetalleVenta
from app.modules.ventas.domain.value_objects import MetodoPago, EstadoVenta
import uuid
from datetime import datetime, timezone


def test_cambio_se_calcula():
    p = Pago.crear(Decimal("36.00"), MetodoPago.EFECTIVO, monto_recibido=Decimal("50.00"))
    assert p.cambio == Decimal("14.00")


def test_sin_monto_recibido_cambio_cero():
    p = Pago.crear(Decimal("36.00"), MetodoPago.EFECTIVO)
    assert p.monto_recibido is None
    assert p.cambio == Decimal("0")


def test_recibido_menor_al_monto_falla():
    with pytest.raises(ValueError):
        Pago.crear(Decimal("36.00"), MetodoPago.EFECTIVO, monto_recibido=Decimal("30.00"))


def test_venta_agrega_efectivo_recibido_y_cambio():
    linea = DetalleVenta(id=uuid.uuid4(), venta_id=uuid.uuid4(), producto_id=uuid.uuid4(),
                         cantidad=Decimal("1"), precio_unitario=Decimal("36"))
    v = Venta(id=uuid.uuid4(), sucursal_id=uuid.uuid4(), caja_turno_id=uuid.uuid4(),
              usuario_id=uuid.uuid4(), cliente_id=None, estado=EstadoVenta.PAGADA,
              lineas=[linea],
              pagos=[Pago.crear(Decimal("36"), MetodoPago.EFECTIVO, monto_recibido=Decimal("50"))],
              created_at=datetime.now(timezone.utc))
    assert v.efectivo_recibido == Decimal("50")
    assert v.cambio == Decimal("14")
