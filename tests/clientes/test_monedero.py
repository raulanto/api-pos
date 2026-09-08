"""Monedero: entidad `MonederoCuenta` y `AjustarMonederoUseCase`."""
import uuid
from decimal import Decimal

import pytest

from app.modules.clientes.domain.entities import MonederoCuenta
from app.modules.clientes.domain.value_objects import TipoMovimientoMonedero
from app.modules.clientes.domain.exceptions import (
    SaldoMonederoInsuficiente, MovimientoMonederoInvalido,
)
from app.modules.clientes.application.use_cases.gestionar_monedero import (
    AjustarMonederoUseCase, AjustarMonederoInput,
)


# --- entidad --------------------------------------------------------------- #
def test_acreditar_y_debitar_mueven_el_saldo():
    c = MonederoCuenta.crear("5550001111")
    c.acreditar(Decimal("100"))
    c.debitar(Decimal("30"))
    assert c.saldo == Decimal("70")


def test_debitar_de_mas_falla():
    c = MonederoCuenta.crear("555")
    c.acreditar(Decimal("10"))
    with pytest.raises(SaldoMonederoInsuficiente):
        c.debitar(Decimal("10.01"))


def test_debitar_hasta_hace_tope_en_el_saldo():
    c = MonederoCuenta.crear("555")
    c.acreditar(Decimal("10"))
    quitado = c.debitar_hasta(Decimal("25"))
    assert quitado == Decimal("10")
    assert c.saldo == Decimal("0")


def test_ajuste_negativo_no_deja_saldo_negativo():
    c = MonederoCuenta.crear("555")
    c.acreditar(Decimal("5"))
    with pytest.raises(SaldoMonederoInsuficiente):
        c.ajustar(Decimal("-6"))
    with pytest.raises(MovimientoMonederoInvalido):
        c.ajustar(Decimal("0"))


# --- caso de uso --------------------------------------------------------- #
class _FakeMonederoRepo:
    def __init__(self):
        self.cuenta: MonederoCuenta | None = None
        self.movimientos: list = []

    async def obtener_por_telefono(self, telefono, para_actualizar=False):
        return self.cuenta

    async def crear_cuenta(self, cuenta):
        self.cuenta = cuenta

    async def guardar_saldo(self, cuenta):
        self.cuenta = cuenta

    async def registrar_movimiento(self, movimiento):
        self.movimientos.append(movimiento)

    async def listar_movimientos(self, cuenta_id, paginacion, orden):  # pragma: no cover
        raise NotImplementedError

    async def movimientos_de_venta(self, venta_id):  # pragma: no cover
        raise NotImplementedError


async def test_ajustar_crea_la_cuenta_y_registra_movimiento():
    repo = _FakeMonederoRepo()
    uc = AjustarMonederoUseCase(repo)
    cuenta = await uc.ejecutar(AjustarMonederoInput(
        telefono="5550009999", monto=Decimal("150"), motivo="carga inicial",
        usuario_id=uuid.uuid4(),
    ))
    assert cuenta.saldo == Decimal("150")
    assert len(repo.movimientos) == 1
    assert repo.movimientos[0].tipo == TipoMovimientoMonedero.AJUSTE
    assert repo.movimientos[0].saldo_resultante == Decimal("150")
