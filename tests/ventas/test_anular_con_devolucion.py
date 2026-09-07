"""No se puede anular una venta que ya tiene devoluciones."""
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.modules.ventas.domain.entities import Venta, DetalleVenta
from app.modules.ventas.domain.value_objects import EstadoVenta
from app.modules.ventas.domain.exceptions import AnulacionNoPermitida
from app.modules.ventas.application.use_cases.anular_venta import (
    AnularVentaUseCase, AnularVentaInput,
)


def _venta():
    l = DetalleVenta(id=uuid.uuid4(), venta_id=uuid.uuid4(), producto_id=uuid.uuid4(),
                     cantidad=Decimal("1"), precio_unitario=Decimal("10"))
    v = Venta(id=uuid.uuid4(), sucursal_id=uuid.uuid4(), caja_turno_id=uuid.uuid4(),
              usuario_id=uuid.uuid4(), cliente_id=None, estado=EstadoVenta.PAGADA,
              lineas=[l], pagos=[], created_at=datetime.now(timezone.utc))
    l.venta_id = v.id
    return v


class _VentaRepo:
    def __init__(self, v): self._v = v
    async def obtener_por_id(self, vid, includes=frozenset()): return self._v


class _DevRepo:
    def __init__(self, hay): self._hay = hay
    async def listar_por_venta(self, vid):
        return [object()] if self._hay else []


async def test_anular_con_devolucion_falla():
    v = _venta()
    uc = AnularVentaUseCase(_VentaRepo(v), None, None, None, None, devolucion_repo=_DevRepo(True))
    with pytest.raises(AnulacionNoPermitida):
        await uc.ejecutar(AnularVentaInput(venta_id=v.id, usuario_id=v.usuario_id,
                                           puede_anular_cerradas=True))
