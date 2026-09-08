"""Movimientos de caja (retiro / ingreso / gasto) y su efecto en el arqueo."""
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.modules.ventas.domain.entities import (
    CajaTurno, CajaMovimiento, ESTADO_TURNO_ABIERTO, ESTADO_TURNO_CERRADO,
)
from app.modules.ventas.domain.value_objects import TipoMovimientoCaja
from app.modules.ventas.domain.exceptions import (
    MotivoMovimientoRequerido, MovimientoTurnoCerrado, CierreTurnoNoPermitido,
)
from app.modules.ventas.application.use_cases.gestionar_caja import (
    RegistrarMovimientoCajaUseCase, RegistrarMovimientoCajaInput,
    ObtenerResumenTurnoUseCase,
)

SUC = uuid.uuid4()
USER = uuid.uuid4()
TURNO = uuid.uuid4()


def _turno(estado=ESTADO_TURNO_ABIERTO, usuario_id=USER):
    return CajaTurno(
        id=TURNO, sucursal_id=SUC, caja_id=uuid.uuid4(), usuario_id=usuario_id,
        saldo_inicial=Decimal("1000"), estado=estado,
        abierto_en=datetime.now(timezone.utc),
    )


class _TurnoRepo:
    def __init__(self, turno):
        self._t = turno
        self.movimientos: list[CajaMovimiento] = []

    async def obtener_por_id(self, tid):
        return self._t

    async def registrar_movimiento(self, mov):
        self.movimientos.append(mov)

    async def listar_movimientos(self, tid):
        return list(self.movimientos)

    async def movimientos_por_tipo(self, tid):
        out: dict[str, Decimal] = {}
        for m in self.movimientos:
            out[m.tipo.value] = out.get(m.tipo.value, Decimal("0")) + m.monto
        return out

    async def movimientos_neto_del_turno(self, tid):
        por_tipo = await self.movimientos_por_tipo(tid)
        return (
            por_tipo.get("ingreso", Decimal("0"))
            - por_tipo.get("retiro", Decimal("0"))
            - por_tipo.get("gasto", Decimal("0"))
        )

    async def total_efectivo_del_turno(self, tid):
        return Decimal("0")

    async def total_devoluciones_efectivo_del_turno(self, tid):
        return Decimal("0")

    async def contar_ventas_del_turno(self, tid):
        return 0

    async def listar_denominaciones(self, tid, momento=None):
        return []


class _Event:
    def __init__(self):
        self.publicados = []

    async def publicar(self, nombre, payload):
        self.publicados.append((nombre, payload))


async def test_retiro_sin_motivo_falla():
    uc = RegistrarMovimientoCajaUseCase(_TurnoRepo(_turno()))
    with pytest.raises(MotivoMovimientoRequerido):
        await uc.ejecutar(RegistrarMovimientoCajaInput(
            TURNO, USER, TipoMovimientoCaja.RETIRO, Decimal("500"),
        ))


async def test_gasto_sin_motivo_falla():
    uc = RegistrarMovimientoCajaUseCase(_TurnoRepo(_turno()))
    with pytest.raises(MotivoMovimientoRequerido):
        await uc.ejecutar(RegistrarMovimientoCajaInput(
            TURNO, USER, TipoMovimientoCaja.GASTO, Decimal("50"),
        ))


async def test_ingreso_sin_motivo_ok_y_se_audita():
    ev = _Event()
    uc = RegistrarMovimientoCajaUseCase(_TurnoRepo(_turno()), ev)
    mov = await uc.ejecutar(RegistrarMovimientoCajaInput(
        TURNO, USER, TipoMovimientoCaja.INGRESO, Decimal("200"),
    ))
    assert mov.tipo == TipoMovimientoCaja.INGRESO
    assert ev.publicados and ev.publicados[0][0] == "MovimientoCajaRegistrado"


async def test_monto_no_positivo_falla():
    uc = RegistrarMovimientoCajaUseCase(_TurnoRepo(_turno()))
    with pytest.raises(ValueError):
        await uc.ejecutar(RegistrarMovimientoCajaInput(
            TURNO, USER, TipoMovimientoCaja.INGRESO, Decimal("0"),
        ))


async def test_movimiento_en_turno_cerrado_falla():
    uc = RegistrarMovimientoCajaUseCase(_TurnoRepo(_turno(estado=ESTADO_TURNO_CERRADO)))
    with pytest.raises(MovimientoTurnoCerrado):
        await uc.ejecutar(RegistrarMovimientoCajaInput(
            TURNO, USER, TipoMovimientoCaja.INGRESO, Decimal("10"),
        ))


async def test_movimiento_en_turno_ajeno_sin_permiso_falla():
    uc = RegistrarMovimientoCajaUseCase(_TurnoRepo(_turno(usuario_id=uuid.uuid4())))
    with pytest.raises(CierreTurnoNoPermitido):
        await uc.ejecutar(RegistrarMovimientoCajaInput(
            TURNO, USER, TipoMovimientoCaja.INGRESO, Decimal("10"),
        ))


async def test_resumen_refleja_ingresos_retiros_gastos():
    repo = _TurnoRepo(_turno())
    uc = RegistrarMovimientoCajaUseCase(repo)
    await uc.ejecutar(RegistrarMovimientoCajaInput(
        TURNO, USER, TipoMovimientoCaja.INGRESO, Decimal("200"),
    ))
    await uc.ejecutar(RegistrarMovimientoCajaInput(
        TURNO, USER, TipoMovimientoCaja.RETIRO, Decimal("500"), motivo="a caja fuerte",
    ))
    await uc.ejecutar(RegistrarMovimientoCajaInput(
        TURNO, USER, TipoMovimientoCaja.GASTO, Decimal("50"), motivo="papelería",
    ))
    resumen = await ObtenerResumenTurnoUseCase(repo).ejecutar(TURNO)
    # neto = 200 - 500 - 50 = -350 ; saldo_esperado = 1000 + 0 - 0 + (-350)
    assert resumen.movimientos_neto == Decimal("-350")
    assert resumen.saldo_esperado == Decimal("650")
    assert resumen.total_retiros == Decimal("500")
