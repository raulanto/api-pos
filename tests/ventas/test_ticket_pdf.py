"""Ticket: armado de datos + render a PDF."""
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from app.modules.ventas.domain.entities import Venta, DetalleVenta, Pago
from app.modules.ventas.domain.value_objects import EstadoVenta, MetodoPago
from app.modules.ventas.application.use_cases.generar_ticket import (
    GenerarTicketUseCase, TicketData, TicketLinea, TicketPago,
)
from app.modules.ventas.infrastructure.pdf.ticket_pdf import render_ticket_pdf

PROD = uuid.uuid4()
SUC = uuid.uuid4()


def _venta():
    l = DetalleVenta(id=uuid.uuid4(), venta_id=uuid.uuid4(), producto_id=PROD,
                     cantidad=Decimal("2"), precio_unitario=Decimal("18"),
                     promo_descuento=Decimal("3"), promo_etiqueta="2x1")
    v = Venta(id=uuid.uuid4(), sucursal_id=SUC, caja_turno_id=uuid.uuid4(),
              usuario_id=uuid.uuid4(), cliente_id=None, estado=EstadoVenta.PAGADA,
              lineas=[l],
              pagos=[Pago.crear(Decimal("33"), MetodoPago.EFECTIVO, monto_recibido=Decimal("50"))],
              created_at=datetime.now(timezone.utc))
    l.venta_id = v.id
    return v


class _VentaRepo:
    def __init__(self, v): self._v = v
    async def obtener_por_id(self, vid, includes=frozenset()):
        return self._v if self._v.id == vid else None


class _ProdRepo:
    async def obtener_por_id(self, pid, includes=frozenset()):
        return type("P", (), {"nombre": "Refresco Cola"})()


class _SucRepo:
    async def obtener_por_id(self, sid):
        return type("S", (), {"nombre": "Sucursal Centro", "direccion": "Calle 1",
                              "telefono": "555-0100"})()


async def test_arma_ticket_data():
    v = _venta()
    data = await GenerarTicketUseCase(_VentaRepo(v), _ProdRepo(), _SucRepo()).ejecutar(v.id)
    assert data.sucursal_nombre == "Sucursal Centro"
    assert data.lineas[0].nombre == "Refresco Cola"
    assert data.lineas[0].importe == Decimal("33")          # 2*18 - 3
    assert data.total == Decimal("33")
    assert data.pagos[0].cambio == Decimal("17")            # 50 - 33
    assert data.cambio == Decimal("17")


def test_render_devuelve_pdf():
    data = TicketData(
        venta_id=uuid.uuid4(), sucursal_id=SUC, folio="abcd1234",
        fecha=datetime.now(timezone.utc), estado="pagada",
        sucursal_nombre="S", sucursal_direccion="dir", sucursal_telefono="tel",
        cliente_nombre=None,
        lineas=[TicketLinea("Prod", Decimal("2"), Decimal("18"), Decimal("3"), "2x1", Decimal("33"))],
        subtotal=Decimal("33"), descuento_total=Decimal("0"),
        total_promociones=Decimal("3"), total=Decimal("33"), total_devuelto=Decimal("0"),
        pagos=[TicketPago("efectivo", Decimal("33"), Decimal("50"), Decimal("17"))],
        total_pagado=Decimal("33"), cambio=Decimal("17"), saldo_pendiente=Decimal("0"),
    )
    pdf = render_ticket_pdf(data)
    assert isinstance(pdf, bytes) and pdf[:4] == b"%PDF"
