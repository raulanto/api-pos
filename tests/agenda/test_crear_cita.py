"""`CrearCitaUseCase`: valida el servicio, calcula fin, resuelve recurso y
oferta en paralelo a los empleados elegibles."""
import uuid
from datetime import datetime, time, timezone
from decimal import Decimal

import pytest

from app.modules.agenda.domain.value_objects import EstadoCita, EstadoAsignacion
from app.modules.agenda.domain.exceptions import ServicioNoAgendable, SucursalCruzadaNoPermitida
from app.modules.agenda.application.use_cases.crear_cita import CrearCitaUseCase, CrearCitaInput
from app.modules.agenda.domain.entities import HorarioBase
from app.modules.inventario.domain.entities import Producto
from app.modules.inventario.domain.value_objects import TipoProducto

SUC = uuid.uuid4()
SERVICIO = uuid.uuid4()
USER = uuid.uuid4()
EMP1 = uuid.uuid4()
EMP2 = uuid.uuid4()
INICIO = datetime(2026, 9, 14, 16, 0, tzinfo=timezone.utc)   # lunes 10:00 hora Mexico City


def _servicio(**kw):
    base = dict(
        sku="SRV", nombre="Corte", categoria_id=uuid.uuid4(), unidad_medida="servicio",
        precio_venta=Decimal("200"), costo=Decimal("0"), impuesto_tasa=Decimal("0"),
        tipo=TipoProducto.SERVICIO, duracion_minutos=30,
    )
    base.update(kw)
    return Producto.crear(**base)


class _ProductoRepo:
    def __init__(self, producto):
        self._p = producto

    async def obtener_por_id(self, pid, includes=frozenset()):
        return self._p


class _CitaRepo:
    def __init__(self):
        self.guardadas = []

    async def guardar(self, cita):
        self.guardadas.append(cita)


class _RecursoRepo:
    def __init__(self, libres=None):
        self._libres = libres if libres is not None else []

    async def obtener_por_id(self, rid):
        return None

    async def recursos_libres_de(self, sucursal_id, inicio, fin):
        return self._libres


class _DispRepo:
    def __init__(self, calificados=None, horarios=None):
        self._calificados = calificados or []
        self._horarios = horarios or {}

    async def empleados_calificados(self, servicio_id):
        return list(self._calificados)

    async def empleados_ocupados_en(self, empleado_ids, inicio, fin):
        return set()

    async def horarios_de(self, empleado_ids, sucursal_id):
        return {e: self._horarios.get(e, []) for e in empleado_ids}

    async def excepciones_de(self, empleado_ids, fecha):
        return {e: [] for e in empleado_ids}


def _uc(producto, calificados=None, horarios=None, libres_recurso=None):
    return CrearCitaUseCase(
        _CitaRepo(), _ProductoRepo(producto), _RecursoRepo(libres_recurso),
        _DispRepo(calificados, horarios),
    )


async def test_servicio_sin_duracion_no_es_agendable():
    with pytest.raises(ServicioNoAgendable):
        await _uc(_servicio(duracion_minutos=None)).ejecutar(CrearCitaInput(
            servicio_id=SERVICIO, sucursal_id=SUC, fecha_hora_inicio=INICIO,
            creado_por_usuario_id=USER,
        ))


async def test_sin_calificados_queda_sin_empleado_disponible():
    cita = await _uc(_servicio(), calificados=[]).ejecutar(CrearCitaInput(
        servicio_id=SERVICIO, sucursal_id=SUC, fecha_hora_inicio=INICIO,
        creado_por_usuario_id=USER,
    ))
    assert cita.estado == EstadoCita.SIN_EMPLEADO_DISPONIBLE
    assert cita.asignaciones == []


async def test_calificados_dentro_de_horario_generan_ofertas_paralelas():
    horarios = {
        EMP1: [HorarioBase.crear(EMP1, SUC, 0, time(9, 0), time(18, 0))],
        EMP2: [HorarioBase.crear(EMP2, SUC, 0, time(9, 0), time(18, 0))],
    }
    cita = await _uc(_servicio(), calificados=[EMP1, EMP2], horarios=horarios).ejecutar(CrearCitaInput(
        servicio_id=SERVICIO, sucursal_id=SUC, fecha_hora_inicio=INICIO,
        creado_por_usuario_id=USER,
    ))
    assert cita.estado == EstadoCita.POR_ASIGNAR
    assert len(cita.asignaciones) == 2
    assert all(a.estado == EstadoAsignacion.OFRECIDA for a in cita.asignaciones)
    # fin = inicio + 30 min de duración (sin buffer configurado)
    assert (cita.fecha_hora_fin - cita.fecha_hora_inicio).total_seconds() == 30 * 60


async def test_calificado_fuera_de_horario_no_es_candidato():
    horarios = {EMP1: [HorarioBase.crear(EMP1, SUC, 0, time(20, 0), time(23, 0))]}
    cita = await _uc(_servicio(), calificados=[EMP1], horarios=horarios).ejecutar(CrearCitaInput(
        servicio_id=SERVICIO, sucursal_id=SUC, fecha_hora_inicio=INICIO,
        creado_por_usuario_id=USER,
    ))
    assert cita.estado == EstadoCita.SIN_EMPLEADO_DISPONIBLE


async def test_cruzada_no_permitida_si_el_servicio_no_la_activa():
    with pytest.raises(SucursalCruzadaNoPermitida):
        await _uc(_servicio(disponibilidad_cruzada_activa=False)).ejecutar(CrearCitaInput(
            servicio_id=SERVICIO, sucursal_id=SUC, fecha_hora_inicio=INICIO,
            creado_por_usuario_id=USER, disponibilidad_cruzada=True,
        ))


async def test_requiere_recurso_sin_libre_queda_sin_empleado_disponible():
    horarios = {EMP1: [HorarioBase.crear(EMP1, SUC, 0, time(9, 0), time(18, 0))]}
    cita = await _uc(
        _servicio(requiere_recurso=True), calificados=[EMP1], horarios=horarios, libres_recurso=[],
    ).ejecutar(CrearCitaInput(
        servicio_id=SERVICIO, sucursal_id=SUC, fecha_hora_inicio=INICIO,
        creado_por_usuario_id=USER,
    ))
    assert cita.estado == EstadoCita.SIN_EMPLEADO_DISPONIBLE
    assert cita.recurso_id is None
