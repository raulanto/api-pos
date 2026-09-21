"""Tests unitarios para los casos de uso del módulo de auditoría."""
import uuid
from datetime import datetime, timezone

import pytest

from app.modules.auditoria.application.dtos import FiltroAuditoria
from app.modules.auditoria.application.use_cases.listar_auditoria import (
    ListarAuditoriaUseCase, ObtenerLogAuditoriaUseCase, LogNoEncontrado,
)
from app.modules.auditoria.domain.entities import LogAuditoria
from app.shared.responses import Page, PageParams, Sort


class _FakeAuditoriaRepo:
    def __init__(self, logs: list[LogAuditoria] = None):
        self.logs = {log.id: log for log in (logs or [])}

    async def obtener_por_id(self, log_id: uuid.UUID, includes: frozenset[str] = frozenset()) -> LogAuditoria | None:
        return self.logs.get(log_id)

    async def listar(
        self, filtro: FiltroAuditoria, paginacion: PageParams, orden: Sort, includes: frozenset[str] = frozenset()
    ) -> Page:
        filtrados = list(self.logs.values())
        if filtro.usuario_id is not None:
            filtrados = [l for l in filtrados if l.usuario_id == filtro.usuario_id]
        if filtro.modulo:
            filtrados = [l for l in filtrados if l.modulo == filtro.modulo]
        if filtro.accion:
            filtrados = [l for l in filtrados if l.accion == filtro.accion]
        return Page(items=filtrados[:paginacion.limit], total=len(filtrados))


def _crear_log(modulo="ventas", accion="crear", usuario_id=None) -> LogAuditoria:
    return LogAuditoria.crear(
        usuario_id=usuario_id or uuid.uuid4(),
        modulo=modulo,
        accion=accion,
        entidad="Venta",
        entidad_id=str(uuid.uuid4()),
        detalle={"monto": 100.0},
        ip_address="127.0.0.1",
    )


@pytest.mark.asyncio
async def test_listar_auditoria_use_case():
    log1 = _crear_log(modulo="ventas", accion="crear")
    log2 = _crear_log(modulo="inventario", accion="ajuste")
    repo = _FakeAuditoriaRepo([log1, log2])

    use_case = ListarAuditoriaUseCase(repo)
    resultado = await use_case.ejecutar(
        filtro=FiltroAuditoria(modulo="ventas"),
        paginacion=PageParams(page=1, page_size=10),
        orden=Sort(field="fecha", direction="desc"),
    )

    assert resultado.total == 1
    assert len(resultado.items) == 1
    assert resultado.items[0].modulo == "ventas"


@pytest.mark.asyncio
async def test_obtener_log_auditoria_exito():
    log = _crear_log()
    repo = _FakeAuditoriaRepo([log])

    use_case = ObtenerLogAuditoriaUseCase(repo)
    resultado = await use_case.ejecutar(log.id)

    assert resultado.id == log.id
    assert resultado.modulo == log.modulo


@pytest.mark.asyncio
async def test_obtener_log_auditoria_no_encontrado():
    repo = _FakeAuditoriaRepo([])
    use_case = ObtenerLogAuditoriaUseCase(repo)

    with pytest.raises(LogNoEncontrado):
        await use_case.ejecutar(uuid.uuid4())
