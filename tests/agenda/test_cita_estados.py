"""Máquina de estados de `Cita`: iniciar/completar/cancelar/no-show/vincular_venta."""
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.modules.agenda.domain.entities import Cita
from app.modules.agenda.domain.value_objects import EstadoCita
from app.modules.agenda.domain.exceptions import TransicionCitaInvalida, CitaNoFacturable

SUC = uuid.uuid4()
SERVICIO = uuid.uuid4()
USER = uuid.uuid4()
EMP = uuid.uuid4()
INICIO = datetime.now(timezone.utc)
FIN = INICIO + timedelta(minutes=30)


def _asignada():
    cita = Cita.crear(SERVICIO, SUC, INICIO, FIN, USER)
    cita.ofertar([EMP])
    cita.aceptar(EMP)
    return cita


def test_iniciar_y_completar_ok():
    cita = _asignada()
    cita.iniciar()
    assert cita.estado == EstadoCita.EN_PROCESO
    cita.completar()
    assert cita.estado == EstadoCita.COMPLETADA


def test_completar_directo_desde_asignada_ok():
    cita = _asignada()
    cita.completar()
    assert cita.estado == EstadoCita.COMPLETADA


def test_iniciar_sin_estar_asignada_falla():
    cita = Cita.crear(SERVICIO, SUC, INICIO, FIN, USER)
    with pytest.raises(TransicionCitaInvalida):
        cita.iniciar()


def test_cancelar_es_terminal():
    cita = _asignada()
    cita.cancelar("el cliente avisó")
    assert cita.estado == EstadoCita.CANCELADA
    assert cita.motivo_cancelacion == "el cliente avisó"
    with pytest.raises(TransicionCitaInvalida):
        cita.cancelar()


def test_no_show_solo_desde_asignada():
    cita = _asignada()
    cita.marcar_no_show()
    assert cita.estado == EstadoCita.NO_SHOW
    cita2 = Cita.crear(SERVICIO, SUC, INICIO, FIN, USER)
    with pytest.raises(TransicionCitaInvalida):
        cita2.marcar_no_show()


def test_vincular_venta_exige_completada():
    cita = _asignada()
    with pytest.raises(CitaNoFacturable):
        cita.vincular_venta(uuid.uuid4())
    cita.completar()
    detalle_id = uuid.uuid4()
    cita.vincular_venta(detalle_id)
    assert cita.venta_detalle_id == detalle_id


def test_vincular_venta_dos_veces_falla():
    cita = _asignada()
    cita.completar()
    cita.vincular_venta(uuid.uuid4())
    with pytest.raises(CitaNoFacturable):
        cita.vincular_venta(uuid.uuid4())
