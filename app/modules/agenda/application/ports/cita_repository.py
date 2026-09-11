from abc import ABC, abstractmethod
from uuid import UUID

from app.modules.agenda.domain.entities import Cita
from app.modules.agenda.application.dtos import FiltroCitas
from app.shared.responses import Page, PageParams, Sort


class CitaRepository(ABC):
    @abstractmethod
    async def obtener_por_id(
        self, cita_id: UUID, para_actualizar: bool = False
    ) -> Cita | None: ...

    @abstractmethod
    async def guardar(self, cita: Cita) -> None:
        """Persiste la cita + sus `asignaciones`. Puede lanzar `IntegrityError`
        si choca con el EXCLUDE de `recurso` — lo traduce el use case."""
        ...

    @abstractmethod
    async def actualizar(self, cita: Cita) -> None:
        """Reemplaza estado/empleado_id/venta_detalle_id/etc. y sincroniza
        `asignaciones` (upsert de las nuevas/cambiadas)."""
        ...

    @abstractmethod
    async def listar(
        self, filtro: FiltroCitas, paginacion: PageParams, orden: Sort,
        includes: frozenset[str] = frozenset(),
    ) -> Page: ...
