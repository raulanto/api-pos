"""Anular una venta revierte sus movimientos de monedero."""
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from app.modules.ventas.domain.entities import Venta, DetalleVenta, Pago
from app.modules.ventas.domain.value_objects import EstadoVenta, MetodoPago
from app.modules.ventas.application.use_cases.anular_venta import (
    AnularVentaUseCase, AnularVentaInput,
)

TEL = "5550002222"


def _venta():
    l = DetalleVenta(id=uuid.uuid4(), venta_id=uuid.uuid4(), producto_id=uuid.uuid4(),
                     cantidad=Decimal("1"), precio_unitario=Decimal("10"))
    v = Venta(id=uuid.uuid4(), sucursal_id=uuid.uuid4(), caja_turno_id=uuid.uuid4(),
              usuario_id=uuid.uuid4(), cliente_id=None, estado=EstadoVenta.PAGADA,
              lineas=[l],
              pagos=[Pago.crear(Decimal("10"), MetodoPago.MONEDERO)],
              created_at=datetime.now(timezone.utc), telefono=TEL,
              monedero_generado=Decimal("2"))
    l.venta_id = v.id
    return v


class _VentaRepo:
    def __init__(self, v):
        self._v = v
        self.estado = None

    async def obtener_por_id(self, vid, includes=frozenset()):
        return self._v

    async def actualizar_estado(self, vid, estado):
        self.estado = estado


class _Inventario:
    async def revertir_venta(self, venta_id, usuario_id):
        pass


class _Event:
    async def publicar(self, *a, **kw):
        pass


class _MonederoPort:
    def __init__(self):
        self.revertido = None

    async def revertir_venta(self, telefono, venta_id, usuario_id):
        self.revertido = (telefono, venta_id, usuario_id)


async def test_anular_revierte_el_monedero():
    v = _venta()
    repo = _VentaRepo(v)
    port = _MonederoPort()
    uc = AnularVentaUseCase(repo, None, _Inventario(), None, _Event(), monedero=port)
    await uc.ejecutar(AnularVentaInput(
        venta_id=v.id, usuario_id=v.usuario_id, puede_anular_cerradas=True,
    ))
    assert repo.estado == EstadoVenta.CANCELADA
    assert port.revertido == (TEL, v.id, v.usuario_id)
