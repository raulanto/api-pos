"""`CrearVentaUseCase` + monedero: acumulación, pago con monedero, validación."""
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.modules.ventas.domain.entities import CajaTurno, ESTADO_TURNO_ABIERTO
from app.modules.ventas.domain.value_objects import MetodoPago
from app.modules.clientes.domain.exceptions import (
    SaldoMonederoInsuficiente, MovimientoMonederoInvalido,
)
from app.modules.ventas.application.use_cases.crear_venta import (
    CrearVentaUseCase, CrearVentaInput, CotizarVentaInput, LineaInput, PagoInput,
)

SUC = uuid.uuid4()
PROD = uuid.uuid4()
TURNO = uuid.uuid4()
TEL = "5550001111"


class _CajaRepo:
    async def obtener_por_id(self, tid):
        return CajaTurno(
            id=tid, sucursal_id=SUC, usuario_id=uuid.uuid4(),
            saldo_inicial=Decimal("0"), estado=ESTADO_TURNO_ABIERTO,
            abierto_en=datetime.now(timezone.utc),
        )


class _VentaRepo:
    def __init__(self):
        self.guardada = None
        self.monedero_generado = None

    async def obtener_por_idempotency_key(self, k):
        return None

    async def guardar(self, venta):
        self.guardada = venta

    async def registrar_monedero_generado(self, venta_id, monto):
        self.monedero_generado = (venta_id, monto)


class _Inventario:
    async def precio_mayoreo_aplicable(self, pid, cant):
        return None

    async def convertir_a_base(self, producto_id, cantidad, producto_unidad_id=None):
        return cantidad

    async def stock_disponible(self, producto_id, sucursal_id, producto_unidad_id=None):
        return None

    async def descontar_stock(self, **kw):
        pass


class _Event:
    async def publicar(self, *a, **kw):
        pass


class _MonederoPort:
    """Fake: acumula 5% del subtotal, consume contra un saldo dado."""
    def __init__(self, saldo=Decimal("0"), pct=Decimal("5")):
        self._saldo = saldo
        self._pct = pct
        self.consumido = None
        self.acumulado = None
        self.revertido = None

    async def calcular_acumulacion(self, lineas):
        return sum((l.subtotal * self._pct / 100 for l in lineas), Decimal("0"))

    async def acumular(self, telefono, lineas, venta_id, usuario_id):
        total = await self.calcular_acumulacion(lineas)
        self.acumulado = (telefono, total)
        return total

    async def consumir(self, telefono, monto, venta_id, usuario_id):
        if monto > self._saldo:
            raise SaldoMonederoInsuficiente("no alcanza")
        self._saldo -= monto
        self.consumido = (telefono, monto)

    async def reintegrar(self, telefono, monto, venta_id, usuario_id, motivo):
        self._saldo += monto

    async def revertir_venta(self, telefono, venta_id, usuario_id):
        self.revertido = (telefono, venta_id)


def _input(*, telefono=None, pagos=None, cantidad="2", precio="50"):
    return CrearVentaInput(
        sucursal_id=SUC, caja_turno_id=TURNO, usuario_id=uuid.uuid4(),
        cliente_id=None, descuento_total=Decimal("0"),
        lineas=[LineaInput(producto_id=PROD, cantidad=Decimal(cantidad),
                           precio_unitario=Decimal(precio))],
        pagos=pagos or [PagoInput(monto=Decimal("100"), metodo_pago=MetodoPago.EFECTIVO)],
        telefono=telefono,
    )


def _uc(venta_repo, monedero):
    return CrearVentaUseCase(
        venta_repo, _CajaRepo(), _Inventario(), None, _Event(), monedero=monedero,
    )


async def test_acumula_al_registrar_telefono():
    repo, port = _VentaRepo(), _MonederoPort()
    venta = await _uc(repo, port).ejecutar(_input(telefono=TEL))
    # 2*50 = 100 subtotal ; 5% = 5
    assert venta.monedero_generado == Decimal("5")
    assert repo.monedero_generado == (venta.id, Decimal("5"))
    assert port.acumulado == (TEL, Decimal("5"))


async def test_sin_telefono_no_acumula():
    repo, port = _VentaRepo(), _MonederoPort()
    venta = await _uc(repo, port).ejecutar(_input(telefono=None))
    assert venta.monedero_generado == Decimal("0")
    assert port.acumulado is None
    assert repo.monedero_generado is None


async def test_pago_con_monedero_descuenta_saldo():
    repo = _VentaRepo()
    port = _MonederoPort(saldo=Decimal("40"))
    venta = await _uc(repo, port).ejecutar(_input(
        telefono=TEL,
        pagos=[
            PagoInput(monto=Decimal("40"), metodo_pago=MetodoPago.MONEDERO),
            PagoInput(monto=Decimal("60"), metodo_pago=MetodoPago.EFECTIVO),
        ],
    ))
    assert venta.monedero_usado == Decimal("40")
    assert port.consumido == (TEL, Decimal("40"))
    assert venta.estado.value == "pagada"


async def test_pago_con_monedero_sin_saldo_falla():
    port = _MonederoPort(saldo=Decimal("10"))
    with pytest.raises(SaldoMonederoInsuficiente):
        await _uc(_VentaRepo(), port).ejecutar(_input(
            telefono=TEL,
            pagos=[
                PagoInput(monto=Decimal("40"), metodo_pago=MetodoPago.MONEDERO),
                PagoInput(monto=Decimal("60"), metodo_pago=MetodoPago.EFECTIVO),
            ],
        ))


async def test_pago_con_monedero_sin_telefono_falla():
    with pytest.raises(MovimientoMonederoInvalido):
        await _uc(_VentaRepo(), _MonederoPort(saldo=Decimal("999"))).ejecutar(_input(
            telefono=None,
            pagos=[
                PagoInput(monto=Decimal("40"), metodo_pago=MetodoPago.MONEDERO),
                PagoInput(monto=Decimal("60"), metodo_pago=MetodoPago.EFECTIVO),
            ],
        ))


async def test_sin_monedero_port_comportamiento_intacto():
    uc = CrearVentaUseCase(_VentaRepo(), _CajaRepo(), _Inventario(), None, _Event())
    venta = await uc.ejecutar(_input(telefono=TEL))
    assert venta.monedero_generado == Decimal("0")


async def test_cotizar_informa_monedero_a_generar():
    cot = await _uc(_VentaRepo(), _MonederoPort()).cotizar(CotizarVentaInput(
        sucursal_id=SUC, descuento_total=Decimal("0"),
        lineas=[LineaInput(producto_id=PROD, cantidad=Decimal("2"),
                           precio_unitario=Decimal("50"))],
    ))
    assert cot.monedero_a_generar == Decimal("5")
