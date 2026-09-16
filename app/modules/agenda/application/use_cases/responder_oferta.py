from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.exc import IntegrityError

from app.modules.agenda.domain.entities import Cita
from app.modules.agenda.domain.exceptions import (
    CitaNoEncontrada, AsignacionNoPropia, EmpleadoYaAsignado, RecursoNoDisponible,
)
from app.modules.agenda.application.ports.cita_repository import CitaRepository
from app.modules.agenda.application.ports.disponibilidad_repository import (
    DisponibilidadRepository,
)


@dataclass
class ResponderOfertaInput:
    cita_id: UUID
    empleado_id: UUID


async def _cargar_propia(
    cita_repo: CitaRepository, cita_id: UUID, empleado_id: UUID,
) -> Cita:
    cita = await cita_repo.obtener_por_id(cita_id, para_actualizar=True)
    if cita is None:
        raise CitaNoEncontrada(f"No existe la cita {cita_id}")
    if not any(a.empleado_id == empleado_id for a in cita.asignaciones):
        raise AsignacionNoPropia(
            f"El empleado {empleado_id} no tiene una oferta para la cita {cita_id}."
        )
    return cita


class AceptarOfertaUseCase:
    """El empleado confirma su oferta. Vuelve a chequear (con lock) que no
    tenga ya otra cita ASIGNADA/EN_PROCESO que se solape — el EXCLUDE de BD
    sólo protege al `recurso`, este choque de empleado es de aplicación."""

    def __init__(self, cita_repo: CitaRepository, disponibilidad_repo: DisponibilidadRepository):
        self._cita_repo = cita_repo
        self._disponibilidad_repo = disponibilidad_repo

    async def ejecutar(self, data: ResponderOfertaInput) -> Cita:
        cita = await _cargar_propia(self._cita_repo, data.cita_id, data.empleado_id)

        ocupados = await self._disponibilidad_repo.empleados_ocupados_en(
            [data.empleado_id], cita.fecha_hora_inicio, cita.fecha_hora_fin,
        )
        if data.empleado_id in ocupados:
            raise EmpleadoYaAsignado(
                f"El empleado {data.empleado_id} ya tiene otra cita asignada en ese horario."
            )

        cita.aceptar(data.empleado_id)
        try:
            await self._cita_repo.actualizar(cita)
        except IntegrityError:
            raise RecursoNoDisponible(
                "El recurso de esta cita quedó ocupado por otra cita antes de confirmar."
            )
        return cita


class RechazarOfertaUseCase:
    def __init__(self, cita_repo: CitaRepository):
        self._cita_repo = cita_repo

    async def ejecutar(self, data: ResponderOfertaInput) -> Cita:
        cita = await _cargar_propia(self._cita_repo, data.cita_id, data.empleado_id)
        cita.rechazar(data.empleado_id)
        await self._cita_repo.actualizar(cita)
        return cita
