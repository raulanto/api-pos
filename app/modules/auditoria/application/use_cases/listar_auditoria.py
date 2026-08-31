from uuid import UUID

from app.modules.auditoria.domain.entities import LogAuditoria
from app.modules.auditoria.application.dtos import FiltroAuditoria
from app.modules.auditoria.application.ports.auditoria_repository import AuditoriaRepository
from app.shared.responses import Page, PageParams, Sort


class LogNoEncontrado(Exception):
    pass


class ListarAuditoriaUseCase:
    def __init__(self, repo: AuditoriaRepository):
        self._repo = repo

    async def ejecutar(
        self, filtro: FiltroAuditoria, paginacion: PageParams, orden: Sort
    ) -> Page:
        return await self._repo.listar(filtro, paginacion, orden)


class ObtenerLogAuditoriaUseCase:
    def __init__(self, repo: AuditoriaRepository):
        self._repo = repo

    async def ejecutar(self, log_id: UUID) -> LogAuditoria:
        log = await self._repo.obtener_por_id(log_id)
        if log is None:
            raise LogNoEncontrado(f"No existe el registro de auditoría {log_id}")
        return log
