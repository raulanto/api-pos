from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.auditoria.domain.entities import LogAuditoria
from app.modules.auditoria.application.dtos import FiltroAuditoria
from app.modules.auditoria.application.ports.auditoria_repository import AuditoriaRepository
from app.modules.auditoria.infrastructure.persistence.orm_models import LogAuditoriaORM
from app.shared.responses import Page, PageParams, Sort


def _to_domain(orm: LogAuditoriaORM, includes: frozenset[str] = frozenset()) -> LogAuditoria:
    log = LogAuditoria(
        id=orm.id,
        usuario_id=orm.usuario_id,
        modulo=orm.modulo,
        accion=orm.accion,
        entidad=orm.entidad,
        entidad_id=orm.entidad_id,
        detalle=orm.detalle,
        ip_address=orm.ip_address,
        fecha=orm.fecha,
    )
    if "usuario" in includes:
        log.usuario = orm.usuario
    return log


class SqlAlchemyAuditoriaRepository(AuditoriaRepository):
    _ORDEN = {
        "fecha": LogAuditoriaORM.fecha,
        "modulo": LogAuditoriaORM.modulo,
        "accion": LogAuditoriaORM.accion,
    }

    def __init__(self, db: AsyncSession):
        self._db = db

    def _opts(self, includes: frozenset[str]):
        return [selectinload(LogAuditoriaORM.usuario)] if "usuario" in includes else []

    async def obtener_por_id(
        self, log_id: UUID, includes: frozenset[str] = frozenset()
    ) -> LogAuditoria | None:
        orm = (await self._db.execute(
            select(LogAuditoriaORM).options(*self._opts(includes)).where(LogAuditoriaORM.id == log_id)
        )).scalar_one_or_none()
        return _to_domain(orm, includes) if orm else None

    async def listar(
        self,
        filtro: FiltroAuditoria,
        paginacion: PageParams,
        orden: Sort,
        includes: frozenset[str] = frozenset(),
    ) -> Page:
        condiciones = []
        if filtro.usuario_id is not None:
            condiciones.append(LogAuditoriaORM.usuario_id == filtro.usuario_id)
        if filtro.modulo:
            condiciones.append(LogAuditoriaORM.modulo == filtro.modulo)
        if filtro.accion:
            condiciones.append(LogAuditoriaORM.accion == filtro.accion)
        if filtro.entidad:
            condiciones.append(LogAuditoriaORM.entidad == filtro.entidad)
        if filtro.entidad_id:
            condiciones.append(LogAuditoriaORM.entidad_id == filtro.entidad_id)
        if filtro.desde is not None:
            condiciones.append(LogAuditoriaORM.fecha >= filtro.desde)
        if filtro.hasta is not None:
            condiciones.append(LogAuditoriaORM.fecha <= filtro.hasta)

        col = self._ORDEN.get(orden.field, LogAuditoriaORM.fecha)
        orden_expr = col.desc() if orden.descending else col.asc()

        total = await self._db.scalar(
            select(func.count()).select_from(LogAuditoriaORM).where(*condiciones)
        )
        filas = (await self._db.execute(
            select(LogAuditoriaORM)
            .options(*self._opts(includes))
            .where(*condiciones)
            .order_by(orden_expr)
            .limit(paginacion.limit)
            .offset(paginacion.offset)
        )).scalars().all()
        return Page(items=[_to_domain(o, includes) for o in filas], total=int(total or 0))
