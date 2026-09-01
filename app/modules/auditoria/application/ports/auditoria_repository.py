from abc import ABC, abstractmethod
from uuid import UUID

from app.modules.auditoria.domain.entities import LogAuditoria
from app.modules.auditoria.application.dtos import FiltroAuditoria
from app.shared.responses import Page, PageParams, Sort


class AuditoriaRepository(ABC):
    @abstractmethod
    async def obtener_por_id(
        self, log_id: UUID, includes: frozenset[str] = frozenset()
    ) -> LogAuditoria | None: ...

    @abstractmethod
    async def listar(
        self,
        filtro: FiltroAuditoria,
        paginacion: PageParams,
        orden: Sort,
        includes: frozenset[str] = frozenset(),
    ) -> Page: ...
