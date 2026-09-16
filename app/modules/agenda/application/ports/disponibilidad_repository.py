from abc import ABC, abstractmethod
from datetime import date
from uuid import UUID

from app.modules.agenda.domain.entities import (
    EmpleadoServicio, HorarioBase, ExcepcionDisponibilidad, HorarioRecurso,
)


class DisponibilidadRepository(ABC):
    """CRUD del catálogo de disponibilidad: qué empleados atienden qué
    servicios, sus horarios base y sus excepciones puntuales, y el horario
    propio (opcional) de un recurso."""

    # --- empleado_servicio ---
    @abstractmethod
    async def calificar_empleado(self, es: EmpleadoServicio) -> None: ...

    @abstractmethod
    async def descalificar_empleado(self, empleado_id: UUID, servicio_id: UUID) -> None:
        """Togglea `activo=False` (o crea+desactiva si no existía la fila)."""
        ...

    @abstractmethod
    async def esta_calificado(self, empleado_id: UUID, servicio_id: UUID) -> bool: ...

    @abstractmethod
    async def empleados_calificados(self, servicio_id: UUID) -> list[UUID]: ...

    @abstractmethod
    async def listar_servicios_de(self, empleado_id: UUID) -> list[EmpleadoServicio]: ...

    # --- disponibilidad_horario ---
    @abstractmethod
    async def guardar_horario(self, horario: HorarioBase) -> None: ...

    @abstractmethod
    async def eliminar_horario(self, horario_id: UUID) -> None: ...

    @abstractmethod
    async def horarios_de(
        self, empleado_ids: list[UUID], sucursal_id: UUID | None,
    ) -> dict[UUID, list[HorarioBase]]:
        """`sucursal_id=None` = no filtra por sucursal (disponibilidad cruzada)."""
        ...

    # --- disponibilidad_excepcion ---
    @abstractmethod
    async def guardar_excepcion(self, excepcion: ExcepcionDisponibilidad) -> None: ...

    @abstractmethod
    async def eliminar_excepcion(self, excepcion_id: UUID) -> None: ...

    @abstractmethod
    async def excepciones_de(
        self, empleado_ids: list[UUID], fecha: date,
    ) -> dict[UUID, list[ExcepcionDisponibilidad]]: ...

    # --- disponibilidad_recurso ---
    @abstractmethod
    async def guardar_horario_recurso(self, horario: HorarioRecurso) -> None: ...

    @abstractmethod
    async def horarios_del_recurso(self, recurso_id: UUID) -> list[HorarioRecurso]: ...

    # --- choques con otras citas (empleado) ---
    @abstractmethod
    async def empleados_ocupados_en(
        self, empleado_ids: list[UUID], inicio, fin,
    ) -> set[UUID]:
        """`empleado_id` con una cita ASIGNADA/EN_PROCESO que se solapa con
        [inicio, fin)."""
        ...
