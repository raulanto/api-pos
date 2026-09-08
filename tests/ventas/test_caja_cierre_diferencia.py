"""Cierre de turno con diferencia + flujo de conciliación."""
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.modules.ventas.domain.entities import (
    CajaTurno, ESTADO_TURNO_ABIERTO, ESTADO_TURNO_CERRADO,
    ESTADO_TURNO_CERRADO_CON_DIFERENCIA, ESTADO_TURNO_CONCILIADO,
)
from app.modules.ventas.domain.exceptions import (
    NotaCierreRequerida, TurnoNoRequiereConciliacion, ConciliacionNoPermitida,
)
from app.modules.ventas.application.use_cases.gestionar_caja import (
    CerrarCajaTurnoUseCase, CerrarCajaTurnoInput,
    ConciliarTurnoUseCase, ConciliarTurnoInput,
)

SUC = uuid.uuid4()
USER = uuid.uuid4()
UMBRAL = Decimal("20.00")


def _turno(estado=ESTADO_TURNO_ABIERTO, **kw):
    base = dict(
        id=uuid.uuid4(), sucursal_id=SUC, caja_id=uuid.uuid4(), usuario_id=USER,
        saldo_inicial=Decimal("1000"), estado=estado,
        abierto_en=datetime.now(timezone.utc),
    )
    base.update(kw)
    return CajaTurno(**base)


class _TurnoRepo:
    def __init__(self, turno, efectivo=Decimal("0")):
        self._t = turno
        self._efectivo = efectivo
        self.actualizado = None

    async def obtener_por_id(self, tid):
        return self._t

    async def total_efectivo_del_turno(self, tid):
        return self._efectivo

    async def total_devoluciones_efectivo_del_turno(self, tid):
        return Decimal("0")

    async def movimientos_neto_del_turno(self, tid):
        return Decimal("0")

    async def actualizar(self, turno):
        self.actualizado = turno

    async def guardar_denominaciones(self, tid, momento, conteos):
        pass


async def test_diferencia_menor_al_umbral_cierra_normal():
    repo = _TurnoRepo(_turno(), efectivo=Decimal("500"))
    turno = await CerrarCajaTurnoUseCase(repo, umbral=UMBRAL).ejecutar(
        CerrarCajaTurnoInput(repo._t.id, USER, saldo_final_declarado=Decimal("1490")),
    )
    # esperado 1500, declarado 1490 -> dif -10, |dif| < 20
    assert turno.estado == ESTADO_TURNO_CERRADO
    assert turno.diferencia == Decimal("-10")


async def test_diferencia_sobre_umbral_sin_nota_falla():
    repo = _TurnoRepo(_turno(), efectivo=Decimal("500"))
    with pytest.raises(NotaCierreRequerida):
        await CerrarCajaTurnoUseCase(repo, umbral=UMBRAL).ejecutar(
            CerrarCajaTurnoInput(repo._t.id, USER, saldo_final_declarado=Decimal("1450")),
        )


async def test_diferencia_sobre_umbral_con_nota_queda_para_conciliar():
    repo = _TurnoRepo(_turno(), efectivo=Decimal("500"))
    turno = await CerrarCajaTurnoUseCase(repo, umbral=UMBRAL).ejecutar(
        CerrarCajaTurnoInput(
            repo._t.id, USER, saldo_final_declarado=Decimal("1450"),
            nota_cierre="faltante, se reporta a gerencia",
        ),
    )
    assert turno.estado == ESTADO_TURNO_CERRADO_CON_DIFERENCIA
    assert turno.requiere_conciliacion


async def test_conciliar_sin_permiso_falla():
    repo = _TurnoRepo(_turno(
        estado=ESTADO_TURNO_CERRADO_CON_DIFERENCIA, diferencia=Decimal("-30"),
    ))
    with pytest.raises(ConciliacionNoPermitida):
        await ConciliarTurnoUseCase(repo).ejecutar(
            ConciliarTurnoInput(repo._t.id, uuid.uuid4(), puede_conciliar=False),
        )


async def test_conciliar_ok_marca_quien_y_cuando():
    gerente = uuid.uuid4()
    repo = _TurnoRepo(_turno(
        estado=ESTADO_TURNO_CERRADO_CON_DIFERENCIA, diferencia=Decimal("-30"),
        nota_cierre="faltante",
    ))
    turno = await ConciliarTurnoUseCase(repo).ejecutar(ConciliarTurnoInput(
        repo._t.id, gerente, puede_conciliar=True, nota="autorizado, se descuenta a caja chica",
    ))
    assert turno.estado == ESTADO_TURNO_CONCILIADO
    assert turno.conciliado_por == gerente and turno.conciliado_en is not None
    assert "autorizado" in turno.nota_cierre


async def test_conciliar_turno_sin_diferencia_falla():
    repo = _TurnoRepo(_turno(estado=ESTADO_TURNO_CERRADO, diferencia=Decimal("0")))
    with pytest.raises(TurnoNoRequiereConciliacion):
        await ConciliarTurnoUseCase(repo).ejecutar(
            ConciliarTurnoInput(repo._t.id, uuid.uuid4(), puede_conciliar=True),
        )
