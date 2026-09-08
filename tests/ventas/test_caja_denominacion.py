"""Desglose por denominación: su suma tiene que cuadrar con el saldo declarado."""
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.modules.ventas.domain.entities import (
    Caja, CajaTurno, DenominacionConteo, ESTADO_TURNO_ABIERTO,
)
from app.modules.ventas.domain.exceptions import DenominacionNoCuadra
from app.modules.ventas.application.use_cases.gestionar_caja import (
    AbrirCajaTurnoUseCase, AbrirCajaTurnoInput,
    CerrarCajaTurnoUseCase, CerrarCajaTurnoInput,
)

SUC = uuid.uuid4()
USER = uuid.uuid4()


class _TerminalRepo:
    def __init__(self, caja):
        self._c = caja

    async def obtener_por_id(self, cid):
        return self._c


class _TurnoRepo:
    def __init__(self, turno=None):
        self._t = turno
        self.denominaciones: dict[str, list] = {}

    async def obtener_abierto_de_usuario(self, uid, sid):
        return None

    async def guardar(self, turno):
        self._t = turno

    async def obtener_por_id(self, tid):
        return self._t

    async def total_efectivo_del_turno(self, tid):
        return Decimal("0")

    async def total_devoluciones_efectivo_del_turno(self, tid):
        return Decimal("0")

    async def movimientos_neto_del_turno(self, tid):
        return Decimal("0")

    async def actualizar(self, turno):
        self._t = turno

    async def guardar_denominaciones(self, tid, momento, conteos):
        self.denominaciones[momento] = list(conteos)


def _turno_abierto():
    return CajaTurno(
        id=uuid.uuid4(), sucursal_id=SUC, caja_id=uuid.uuid4(), usuario_id=USER,
        saldo_inicial=Decimal("1000"), estado=ESTADO_TURNO_ABIERTO,
        abierto_en=datetime.now(timezone.utc),
    )


async def test_apertura_desglose_no_cuadra_falla():
    caja = Caja.crear(SUC, "Caja 1")
    uc = AbrirCajaTurnoUseCase(_TurnoRepo(), None, None, _TerminalRepo(caja))
    with pytest.raises(DenominacionNoCuadra):
        await uc.ejecutar(AbrirCajaTurnoInput(
            sucursal_id=SUC, caja_id=caja.id, usuario_id=USER,
            saldo_inicial=Decimal("1000"),
            denominaciones=[DenominacionConteo(Decimal("500"), 1)],  # suma 500 != 1000
        ))


async def test_apertura_desglose_cuadra_persiste():
    caja = Caja.crear(SUC, "Caja 1")
    repo = _TurnoRepo()
    uc = AbrirCajaTurnoUseCase(repo, None, None, _TerminalRepo(caja))
    await uc.ejecutar(AbrirCajaTurnoInput(
        sucursal_id=SUC, caja_id=caja.id, usuario_id=USER,
        saldo_inicial=Decimal("1000"),
        denominaciones=[
            DenominacionConteo(Decimal("500"), 1),
            DenominacionConteo(Decimal("100"), 5),
        ],
    ))
    assert len(repo.denominaciones["apertura"]) == 2


async def test_cierre_desglose_no_cuadra_falla():
    repo = _TurnoRepo(_turno_abierto())
    uc = CerrarCajaTurnoUseCase(repo, umbral=Decimal("20"))
    with pytest.raises(DenominacionNoCuadra):
        await uc.ejecutar(CerrarCajaTurnoInput(
            repo._t.id, USER, saldo_final_declarado=Decimal("1000"),
            denominaciones=[DenominacionConteo(Decimal("500"), 1)],  # 500 != 1000
        ))
