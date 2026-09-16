"""Motor puro de disponibilidad (`empleado_disponible`): sólo aritmética de
horarios/excepciones, sin BD."""
import uuid
from datetime import date, time

from app.modules.agenda.domain.entities import HorarioBase, ExcepcionDisponibilidad
from app.modules.agenda.domain.value_objects import TipoExcepcion
from app.modules.agenda.domain.services import empleado_disponible

EMP = uuid.uuid4()
SUC = uuid.uuid4()
LUNES = 0
MARTES = 1
HOY = date(2026, 9, 14)   # un lunes


def _horario(dia, hi, hf):
    return HorarioBase.crear(EMP, SUC, dia, hi, hf)


def test_dentro_del_horario_base_ok():
    horarios = [_horario(LUNES, time(9, 0), time(18, 0))]
    assert empleado_disponible(horarios, [], LUNES, HOY, time(10, 0), time(11, 0))


def test_fuera_del_horario_base_falla():
    horarios = [_horario(LUNES, time(9, 0), time(18, 0))]
    assert not empleado_disponible(horarios, [], LUNES, HOY, time(19, 0), time(20, 0))


def test_otro_dia_de_la_semana_falla():
    horarios = [_horario(MARTES, time(9, 0), time(18, 0))]
    assert not empleado_disponible(horarios, [], LUNES, HOY, time(10, 0), time(11, 0))


def test_bloqueo_total_del_dia_descarta():
    horarios = [_horario(LUNES, time(9, 0), time(18, 0))]
    excepciones = [ExcepcionDisponibilidad.crear(EMP, HOY, TipoExcepcion.BLOQUEO)]
    assert not empleado_disponible(horarios, excepciones, LUNES, HOY, time(10, 0), time(11, 0))


def test_bloqueo_parcial_que_se_solapa_descarta():
    horarios = [_horario(LUNES, time(9, 0), time(18, 0))]
    excepciones = [ExcepcionDisponibilidad.crear(
        EMP, HOY, TipoExcepcion.BLOQUEO, time(10, 30), time(12, 0),
    )]
    assert not empleado_disponible(horarios, excepciones, LUNES, HOY, time(10, 0), time(11, 0))


def test_bloqueo_parcial_que_no_se_solapa_no_descarta():
    horarios = [_horario(LUNES, time(9, 0), time(18, 0))]
    excepciones = [ExcepcionDisponibilidad.crear(
        EMP, HOY, TipoExcepcion.BLOQUEO, time(14, 0), time(15, 0),
    )]
    assert empleado_disponible(horarios, excepciones, LUNES, HOY, time(10, 0), time(11, 0))


def test_horario_especial_reemplaza_al_base():
    # sin horario base ese día, pero con un horario especial que sí cubre el rango.
    excepciones = [ExcepcionDisponibilidad.crear(
        EMP, HOY, TipoExcepcion.HORARIO_ESPECIAL, time(20, 0), time(23, 0),
    )]
    assert empleado_disponible([], excepciones, LUNES, HOY, time(21, 0), time(22, 0))
    # fuera del horario especial, aunque el horario base normal lo cubriría.
    horarios = [_horario(LUNES, time(0, 0), time(23, 59))]
    assert not empleado_disponible(horarios, excepciones, LUNES, HOY, time(10, 0), time(11, 0))
