from dataclasses import dataclass
from datetime import date, time
from uuid import UUID

from app.modules.agenda.domain.entities import (
    Recurso, EmpleadoServicio, HorarioBase, ExcepcionDisponibilidad, HorarioRecurso,
)
from app.modules.agenda.domain.value_objects import TipoExcepcion
from app.modules.agenda.domain.exceptions import (
    RecursoNoEncontrado, NombreRecursoEnUso,
)
from app.modules.agenda.application.ports.recurso_repository import RecursoRepository
from app.modules.agenda.application.ports.disponibilidad_repository import (
    DisponibilidadRepository,
)


# --------------------------------------------------------------------------- #
# Recurso (mismo patrón que `Caja`/terminales en ventas: nombre único entre
# activos de la sucursal)
# --------------------------------------------------------------------------- #
@dataclass
class CrearRecursoInput:
    sucursal_id: UUID
    nombre: str
    tipo: str | None = None


class CrearRecursoUseCase:
    def __init__(self, repo: RecursoRepository):
        self._repo = repo

    async def ejecutar(self, data: CrearRecursoInput) -> Recurso:
        recurso = Recurso.crear(data.sucursal_id, data.nombre, data.tipo)
        if await self._repo.nombre_en_uso(recurso.sucursal_id, recurso.nombre):
            raise NombreRecursoEnUso(
                f"Ya hay un recurso activo llamado '{recurso.nombre}' en esta sucursal."
            )
        await self._repo.guardar(recurso)
        return recurso


class ListarRecursosUseCase:
    def __init__(self, repo: RecursoRepository):
        self._repo = repo

    async def ejecutar(self, sucursal_id: UUID, incluir_inactivos: bool = False) -> list[Recurso]:
        return await self._repo.listar(sucursal_id, incluir_inactivos)


class RenombrarRecursoUseCase:
    def __init__(self, repo: RecursoRepository):
        self._repo = repo

    async def ejecutar(self, recurso_id: UUID, nombre: str) -> Recurso:
        recurso = await self._repo.obtener_por_id(recurso_id)
        if recurso is None:
            raise RecursoNoEncontrado(f"No existe el recurso {recurso_id}")
        recurso.renombrar(nombre)
        if await self._repo.nombre_en_uso(recurso.sucursal_id, recurso.nombre, excluir_id=recurso.id):
            raise NombreRecursoEnUso(
                f"Ya hay un recurso activo llamado '{recurso.nombre}' en esta sucursal."
            )
        await self._repo.actualizar(recurso)
        return recurso


class DesactivarRecursoUseCase:
    def __init__(self, repo: RecursoRepository):
        self._repo = repo

    async def ejecutar(self, recurso_id: UUID) -> Recurso:
        recurso = await self._repo.obtener_por_id(recurso_id)
        if recurso is None:
            raise RecursoNoEncontrado(f"No existe el recurso {recurso_id}")
        recurso.desactivar()
        await self._repo.actualizar(recurso)
        return recurso


class ReactivarRecursoUseCase:
    def __init__(self, repo: RecursoRepository):
        self._repo = repo

    async def ejecutar(self, recurso_id: UUID) -> Recurso:
        recurso = await self._repo.obtener_por_id(recurso_id)
        if recurso is None:
            raise RecursoNoEncontrado(f"No existe el recurso {recurso_id}")
        if await self._repo.nombre_en_uso(recurso.sucursal_id, recurso.nombre, excluir_id=recurso.id):
            raise NombreRecursoEnUso(
                f"Otro recurso activo ya usa el nombre '{recurso.nombre}'; renombrá o "
                "desactivá esa antes de reactivar."
            )
        recurso.reactivar()
        await self._repo.actualizar(recurso)
        return recurso


# --------------------------------------------------------------------------- #
# empleado_servicio
# --------------------------------------------------------------------------- #
class CalificarEmpleadoUseCase:
    def __init__(self, repo: DisponibilidadRepository):
        self._repo = repo

    async def ejecutar(self, empleado_id: UUID, servicio_id: UUID) -> EmpleadoServicio:
        es = EmpleadoServicio.crear(empleado_id, servicio_id)
        await self._repo.calificar_empleado(es)
        return es


class DescalificarEmpleadoUseCase:
    def __init__(self, repo: DisponibilidadRepository):
        self._repo = repo

    async def ejecutar(self, empleado_id: UUID, servicio_id: UUID) -> None:
        await self._repo.descalificar_empleado(empleado_id, servicio_id)


class ListarServiciosDeEmpleadoUseCase:
    def __init__(self, repo: DisponibilidadRepository):
        self._repo = repo

    async def ejecutar(self, empleado_id: UUID) -> list[EmpleadoServicio]:
        return await self._repo.listar_servicios_de(empleado_id)


# --------------------------------------------------------------------------- #
# disponibilidad_horario / disponibilidad_excepcion / disponibilidad_recurso
# --------------------------------------------------------------------------- #
class CrearHorarioUseCase:
    def __init__(self, repo: DisponibilidadRepository):
        self._repo = repo

    async def ejecutar(
        self, empleado_id: UUID, sucursal_id: UUID, dia_semana: int,
        hora_inicio: time, hora_fin: time,
    ) -> HorarioBase:
        horario = HorarioBase.crear(empleado_id, sucursal_id, dia_semana, hora_inicio, hora_fin)
        await self._repo.guardar_horario(horario)
        return horario


class EliminarHorarioUseCase:
    def __init__(self, repo: DisponibilidadRepository):
        self._repo = repo

    async def ejecutar(self, horario_id: UUID) -> None:
        await self._repo.eliminar_horario(horario_id)


class CrearExcepcionUseCase:
    def __init__(self, repo: DisponibilidadRepository):
        self._repo = repo

    async def ejecutar(
        self, empleado_id: UUID, fecha: date, tipo: TipoExcepcion,
        hora_inicio: time | None = None, hora_fin: time | None = None,
        motivo: str | None = None,
    ) -> ExcepcionDisponibilidad:
        excepcion = ExcepcionDisponibilidad.crear(
            empleado_id, fecha, tipo, hora_inicio, hora_fin, motivo,
        )
        await self._repo.guardar_excepcion(excepcion)
        return excepcion


class EliminarExcepcionUseCase:
    def __init__(self, repo: DisponibilidadRepository):
        self._repo = repo

    async def ejecutar(self, excepcion_id: UUID) -> None:
        await self._repo.eliminar_excepcion(excepcion_id)


class CrearHorarioRecursoUseCase:
    def __init__(self, repo: DisponibilidadRepository):
        self._repo = repo

    async def ejecutar(
        self, recurso_id: UUID, dia_semana: int, hora_inicio: time, hora_fin: time,
    ) -> HorarioRecurso:
        horario = HorarioRecurso.crear(recurso_id, dia_semana, hora_inicio, hora_fin)
        await self._repo.guardar_horario_recurso(horario)
        return horario
