from abc import ABC, abstractmethod
from uuid import UUID

from app.modules.agenda.domain.entities import Recurso


class RecursoRepository(ABC):
    @abstractmethod
    async def obtener_por_id(self, recurso_id: UUID) -> Recurso | None: ...

    @abstractmethod
    async def listar(
        self, sucursal_id: UUID, incluir_inactivos: bool = False
    ) -> list[Recurso]: ...

    @abstractmethod
    async def guardar(self, recurso: Recurso) -> None: ...

    @abstractmethod
    async def actualizar(self, recurso: Recurso) -> None: ...

    @abstractmethod
    async def nombre_en_uso(
        self, sucursal_id: UUID, nombre: str, excluir_id: UUID | None = None
    ) -> bool:
        """True si otro recurso ACTIVO de la sucursal ya usa ese nombre."""
        ...

    @abstractmethod
    async def recursos_libres_de(
        self, sucursal_id: UUID, inicio, fin,
    ) -> list[UUID]:
        """`recurso_id` activos de la sucursal SIN una cita
        asignada/en_proceso que se solape con [inicio, fin)."""
        ...
