from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.exc import IntegrityError

from app.modules.agenda.domain.entities import Cita
from app.modules.agenda.domain.exceptions import (
    CitaNoEncontrada, EmpleadoNoCalificado, EmpleadoYaAsignado, RecursoNoDisponible,
)
from app.modules.agenda.application.dtos import FiltroCitas
from app.modules.agenda.application.ports.cita_repository import CitaRepository
from app.modules.agenda.application.ports.disponibilidad_repository import (
    DisponibilidadRepository,
)
from app.modules.agenda.application.use_cases.crear_cita import _buscar_candidatos
from app.shared.responses import Page, PageParams, Sort


async def _cargar(cita_repo: CitaRepository, cita_id: UUID, para_actualizar: bool = False) -> Cita:
    cita = await cita_repo.obtener_por_id(cita_id, para_actualizar=para_actualizar)
    if cita is None:
        raise CitaNoEncontrada(f"No existe la cita {cita_id}")
    return cita


@dataclass
class AsignarManualInput:
    cita_id: UUID
    empleado_id: UUID


class AsignarManualUseCase:
    """El cajero fuerza el responsable (ej. tras `sin_empleado_disponible`),
    saltando la cola de oferta. Igual valida calificación y solape."""

    def __init__(self, cita_repo: CitaRepository, disponibilidad_repo: DisponibilidadRepository):
        self._cita_repo = cita_repo
        self._disponibilidad_repo = disponibilidad_repo

    async def ejecutar(self, data: AsignarManualInput) -> Cita:
        cita = await _cargar(self._cita_repo, data.cita_id, para_actualizar=True)
        if not await self._disponibilidad_repo.esta_calificado(data.empleado_id, cita.servicio_id):
            raise EmpleadoNoCalificado(
                f"El empleado {data.empleado_id} no está calificado para este servicio."
            )
        ocupados = await self._disponibilidad_repo.empleados_ocupados_en(
            [data.empleado_id], cita.fecha_hora_inicio, cita.fecha_hora_fin,
        )
        if data.empleado_id in ocupados:
            raise EmpleadoYaAsignado(
                f"El empleado {data.empleado_id} ya tiene otra cita asignada en ese horario."
            )
        cita.asignar_manual(data.empleado_id)
        try:
            await self._cita_repo.actualizar(cita)
        except IntegrityError:
            raise RecursoNoDisponible(
                "El recurso de esta cita quedó ocupado por otra cita antes de confirmar."
            )
        return cita


class OfertarDeNuevoUseCase:
    """Reintenta la búsqueda de candidatos (típico tras `sin_empleado_disponible`,
    cuando algún empleado liberó su agenda)."""

    def __init__(
        self, cita_repo: CitaRepository, disponibilidad_repo: DisponibilidadRepository,
    ):
        self._cita_repo = cita_repo
        self._disponibilidad_repo = disponibilidad_repo

    async def ejecutar(self, cita_id: UUID) -> Cita:
        cita = await _cargar(self._cita_repo, cita_id, para_actualizar=True)
        candidatos = await _buscar_candidatos(
            self._disponibilidad_repo, cita.servicio_id, cita.sucursal_id,
            cita.disponibilidad_cruzada, cita.fecha_hora_inicio, cita.fecha_hora_fin,
        )
        cita.ofertar(candidatos)
        await self._cita_repo.actualizar(cita)
        return cita


class IniciarCitaUseCase:
    def __init__(self, cita_repo: CitaRepository):
        self._cita_repo = cita_repo

    async def ejecutar(self, cita_id: UUID) -> Cita:
        cita = await _cargar(self._cita_repo, cita_id, para_actualizar=True)
        cita.iniciar()
        await self._cita_repo.actualizar(cita)
        return cita


class CompletarCitaUseCase:
    def __init__(self, cita_repo: CitaRepository):
        self._cita_repo = cita_repo

    async def ejecutar(self, cita_id: UUID) -> Cita:
        cita = await _cargar(self._cita_repo, cita_id, para_actualizar=True)
        cita.completar()
        await self._cita_repo.actualizar(cita)
        return cita


class CancelarCitaUseCase:
    def __init__(self, cita_repo: CitaRepository):
        self._cita_repo = cita_repo

    async def ejecutar(self, cita_id: UUID, motivo: str | None = None) -> Cita:
        cita = await _cargar(self._cita_repo, cita_id, para_actualizar=True)
        cita.cancelar(motivo)
        await self._cita_repo.actualizar(cita)
        return cita


class MarcarNoShowUseCase:
    def __init__(self, cita_repo: CitaRepository):
        self._cita_repo = cita_repo

    async def ejecutar(self, cita_id: UUID) -> Cita:
        cita = await _cargar(self._cita_repo, cita_id, para_actualizar=True)
        cita.marcar_no_show()
        await self._cita_repo.actualizar(cita)
        return cita


class ObtenerCitaUseCase:
    def __init__(self, cita_repo: CitaRepository):
        self._cita_repo = cita_repo

    async def ejecutar(self, cita_id: UUID) -> Cita:
        return await _cargar(self._cita_repo, cita_id)


class ListarCitasUseCase:
    def __init__(self, cita_repo: CitaRepository):
        self._cita_repo = cita_repo

    async def ejecutar(
        self, filtro: FiltroCitas, paginacion: PageParams, orden: Sort,
        includes: frozenset[str] = frozenset(),
    ) -> Page:
        return await self._cita_repo.listar(filtro, paginacion, orden, includes)
