from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

from app.core.config import settings
from app.modules.agenda.domain.entities import Cita
from app.modules.agenda.domain.exceptions import (
    ServicioNoAgendable, RecursoNoEncontrado, SucursalCruzadaNoPermitida,
)
from app.modules.agenda.domain.services import empleado_disponible
from app.modules.agenda.application.ports.cita_repository import CitaRepository
from app.modules.agenda.application.ports.recurso_repository import RecursoRepository
from app.modules.agenda.application.ports.disponibilidad_repository import (
    DisponibilidadRepository,
)
from app.modules.inventario.application.ports.producto_repository import ProductoRepository
from app.modules.inventario.domain.value_objects import TipoProducto


def _local(momento: datetime) -> datetime:
    try:
        return momento.astimezone(ZoneInfo(settings.app_timezone))
    except Exception:
        return momento.astimezone(ZoneInfo("UTC"))


@dataclass
class CrearCitaInput:
    servicio_id: UUID
    sucursal_id: UUID
    fecha_hora_inicio: datetime
    creado_por_usuario_id: UUID
    cliente_id: UUID | None = None
    recurso_id: UUID | None = None
    disponibilidad_cruzada: bool = False
    politica_cancelacion_horas: int | None = None
    penalizacion_cancelacion: Decimal | None = None


async def _buscar_candidatos(
    disponibilidad_repo: DisponibilidadRepository,
    servicio_id: UUID, sucursal_id: UUID, cruzada: bool,
    inicio: datetime, fin: datetime,
) -> list[UUID]:
    """Empleados calificados para el servicio, libres de otras citas y dentro
    de su horario declarado (excepciones incluidas). `cruzada=True` ignora el
    filtro de sucursal al leer horarios (ver `entities.py`/plan §7)."""
    calificados = await disponibilidad_repo.empleados_calificados(servicio_id)
    if not calificados:
        return []

    ocupados = await disponibilidad_repo.empleados_ocupados_en(calificados, inicio, fin)
    libres = [e for e in calificados if e not in ocupados]
    if not libres:
        return []

    sucursal_filtro = None if cruzada else sucursal_id
    horarios = await disponibilidad_repo.horarios_de(libres, sucursal_filtro)
    local_inicio = _local(inicio)
    local_fin = _local(fin)
    excepciones = await disponibilidad_repo.excepciones_de(libres, local_inicio.date())

    return [
        e for e in libres
        if empleado_disponible(
            horarios.get(e, []), excepciones.get(e, []),
            local_inicio.weekday(), local_inicio.date(),
            local_inicio.time(), local_fin.time(),
        )
    ]


class CrearCitaUseCase:
    def __init__(
        self,
        cita_repo: CitaRepository,
        producto_repo: ProductoRepository,
        recurso_repo: RecursoRepository,
        disponibilidad_repo: DisponibilidadRepository,
    ):
        self._cita_repo = cita_repo
        self._producto_repo = producto_repo
        self._recurso_repo = recurso_repo
        self._disponibilidad_repo = disponibilidad_repo

    async def ejecutar(self, data: CrearCitaInput) -> Cita:
        producto = await self._producto_repo.obtener_por_id(data.servicio_id)
        if (
            producto is None or not producto.activo
            or producto.tipo != TipoProducto.SERVICIO
            or producto.duracion_minutos is None
        ):
            raise ServicioNoAgendable(
                f"El producto {data.servicio_id} no es un servicio agendable "
                "(necesita `tipo=servicio` y `duracion_minutos`)."
            )
        if data.disponibilidad_cruzada and not producto.disponibilidad_cruzada_activa:
            raise SucursalCruzadaNoPermitida(
                "Este servicio no tiene activada la disponibilidad cruzada entre sucursales."
            )

        inicio = data.fecha_hora_inicio
        fin = inicio + timedelta(
            minutes=producto.duracion_minutos + producto.tiempo_buffer_minutos
        )

        recurso_id = data.recurso_id
        if producto.requiere_recurso:
            if recurso_id is not None:
                recurso = await self._recurso_repo.obtener_por_id(recurso_id)
                if (
                    recurso is None or not recurso.activo
                    or recurso.sucursal_id != data.sucursal_id
                ):
                    raise RecursoNoEncontrado(
                        f"No existe el recurso {recurso_id} en esta sucursal."
                    )
            else:
                libres = await self._recurso_repo.recursos_libres_de(data.sucursal_id, inicio, fin)
                recurso_id = libres[0] if libres else None

        candidatos: list[UUID] = []
        if not producto.requiere_recurso or recurso_id is not None:
            candidatos = await _buscar_candidatos(
                self._disponibilidad_repo, data.servicio_id, data.sucursal_id,
                data.disponibilidad_cruzada, inicio, fin,
            )

        cita = Cita.crear(
            servicio_id=data.servicio_id, sucursal_id=data.sucursal_id,
            fecha_hora_inicio=inicio, fecha_hora_fin=fin,
            creado_por_usuario_id=data.creado_por_usuario_id,
            cliente_id=data.cliente_id, recurso_id=recurso_id,
            disponibilidad_cruzada=data.disponibilidad_cruzada,
            politica_cancelacion_horas=data.politica_cancelacion_horas,
            penalizacion_cancelacion=data.penalizacion_cancelacion,
        )
        cita.ofertar(candidatos)     # sin candidatos -> SIN_EMPLEADO_DISPONIBLE, no es un error
        await self._cita_repo.guardar(cita)
        return cita
