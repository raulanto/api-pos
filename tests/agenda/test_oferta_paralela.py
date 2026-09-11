"""Cola de oferta paralela: gana el primero en `aceptar()`; el resto queda
`superada`. `AceptarOfertaUseCase`/`RechazarOfertaUseCase`."""
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.modules.agenda.domain.entities import Cita
from app.modules.agenda.domain.value_objects import EstadoCita, EstadoAsignacion
from app.modules.agenda.domain.exceptions import (
    OfertaNoVigente, AsignacionNoPropia, EmpleadoYaAsignado,
)
from app.modules.agenda.application.use_cases.responder_oferta import (
    AceptarOfertaUseCase, RechazarOfertaUseCase, ResponderOfertaInput,
)

SUC = uuid.uuid4()
SERVICIO = uuid.uuid4()
USER = uuid.uuid4()
EMP1 = uuid.uuid4()
EMP2 = uuid.uuid4()
INICIO = datetime(2026, 9, 14, 10, 0, tzinfo=timezone.utc)
FIN = INICIO + timedelta(minutes=30)


def _cita_ofertada(candidatos=(EMP1, EMP2)):
    cita = Cita.crear(SERVICIO, SUC, INICIO, FIN, USER)
    cita.ofertar(list(candidatos))
    return cita


class _CitaRepo:
    def __init__(self, cita):
        self._c = cita

    async def obtener_por_id(self, cid, para_actualizar=False):
        return self._c if self._c.id == cid else None

    async def actualizar(self, cita):
        pass


class _DispRepo:
    def __init__(self, ocupados=None):
        self._ocupados = ocupados or set()

    async def empleados_ocupados_en(self, empleado_ids, inicio, fin):
        return set(e for e in empleado_ids if e in self._ocupados)


async def test_aceptar_una_oferta_supera_las_demas():
    cita = _cita_ofertada()
    await AceptarOfertaUseCase(_CitaRepo(cita), _DispRepo()).ejecutar(
        ResponderOfertaInput(cita.id, EMP1)
    )
    assert cita.estado == EstadoCita.ASIGNADA
    assert cita.empleado_id == EMP1
    por_empleado = {a.empleado_id: a.estado for a in cita.asignaciones}
    assert por_empleado[EMP1] == EstadoAsignacion.ACEPTADA
    assert por_empleado[EMP2] == EstadoAsignacion.SUPERADA


async def test_aceptar_oferta_ya_superada_falla():
    cita = _cita_ofertada()
    await AceptarOfertaUseCase(_CitaRepo(cita), _DispRepo()).ejecutar(
        ResponderOfertaInput(cita.id, EMP1)
    )
    with pytest.raises(OfertaNoVigente):
        await AceptarOfertaUseCase(_CitaRepo(cita), _DispRepo()).ejecutar(
            ResponderOfertaInput(cita.id, EMP2)
        )


async def test_responder_oferta_ajena_falla():
    cita = _cita_ofertada(candidatos=(EMP1,))
    otro = uuid.uuid4()
    with pytest.raises(AsignacionNoPropia):
        await AceptarOfertaUseCase(_CitaRepo(cita), _DispRepo()).ejecutar(
            ResponderOfertaInput(cita.id, otro)
        )


async def test_rechazar_ultima_oferta_deja_sin_empleado_disponible():
    cita = _cita_ofertada(candidatos=(EMP1,))
    await RechazarOfertaUseCase(_CitaRepo(cita)).ejecutar(ResponderOfertaInput(cita.id, EMP1))
    assert cita.estado == EstadoCita.SIN_EMPLEADO_DISPONIBLE


async def test_rechazar_con_otra_oferta_viva_sigue_por_asignar():
    cita = _cita_ofertada()
    await RechazarOfertaUseCase(_CitaRepo(cita)).ejecutar(ResponderOfertaInput(cita.id, EMP1))
    assert cita.estado == EstadoCita.POR_ASIGNAR


async def test_aceptar_choca_con_otra_cita_del_empleado():
    cita = _cita_ofertada(candidatos=(EMP1,))
    with pytest.raises(EmpleadoYaAsignado):
        await AceptarOfertaUseCase(_CitaRepo(cita), _DispRepo(ocupados={EMP1})).ejecutar(
            ResponderOfertaInput(cita.id, EMP1)
        )
    # la oferta sigue viva: no se consumió por el intento fallido.
    assert cita.estado == EstadoCita.POR_ASIGNAR
