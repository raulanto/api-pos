"""Motor puro de disponibilidad: sólo aritmética de horarios, sin BD. Los
choques con OTRAS citas (empleado ya asignado, recurso ocupado) los resuelve
el repositorio con SQL — acá sólo se decide si el horario declarado del
empleado cubre el rango pedido."""
from datetime import date, time

from app.modules.agenda.domain.entities import HorarioBase, ExcepcionDisponibilidad
from app.modules.agenda.domain.value_objects import TipoExcepcion


def _se_solapan(a_inicio: time, a_fin: time, b_inicio: time, b_fin: time) -> bool:
    return a_inicio < b_fin and b_inicio < a_fin


def _dentro_de_horario(
    horarios: list[HorarioBase], dia_semana: int, hora_inicio: time, hora_fin: time,
) -> bool:
    """¿Algún horario base cubre COMPLETO el rango pedido ese día?"""
    return any(
        h.dia_semana == dia_semana and h.hora_inicio <= hora_inicio and hora_fin <= h.hora_fin
        for h in horarios
    )


def empleado_disponible(
    horarios: list[HorarioBase],
    excepciones: list[ExcepcionDisponibilidad],
    dia_semana: int,
    fecha: date,
    hora_inicio: time,
    hora_fin: time,
) -> bool:
    """Un BLOQUEO (total o que se solapa) descarta al empleado. Si hay un
    HORARIO_ESPECIAL ese día, reemplaza al horario base (debe cubrir el rango
    completo). Si no hay excepciones, manda el horario base recurrente."""
    del_dia = [e for e in excepciones if e.fecha == fecha]

    for e in del_dia:
        if e.tipo == TipoExcepcion.BLOQUEO:
            if e.hora_inicio is None:              # bloqueo total del día
                return False
            if _se_solapan(e.hora_inicio, e.hora_fin, hora_inicio, hora_fin):
                return False

    especial = next((e for e in del_dia if e.tipo == TipoExcepcion.HORARIO_ESPECIAL), None)
    if especial is not None:
        return especial.hora_inicio <= hora_inicio and hora_fin <= especial.hora_fin

    return _dentro_de_horario(horarios, dia_semana, hora_inicio, hora_fin)


def recurso_disponible(
    horarios_recurso: list, dia_semana: int, hora_inicio: time, hora_fin: time,
) -> bool:
    """Sin horarios propios = siempre disponible (el choque real con otras
    citas lo garantiza el EXCLUDE constraint de BD, no esta función)."""
    if not horarios_recurso:
        return True
    return _dentro_de_horario(horarios_recurso, dia_semana, hora_inicio, hora_fin)
