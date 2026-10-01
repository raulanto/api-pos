from uuid import UUID
from typing import Sequence
from datetime import datetime, timezone
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.notificaciones.domain.entities import Notificacion
from app.modules.notificaciones.application.ports.notificacion_repository import NotificacionRepository
from app.modules.notificaciones.infrastructure.persistence.orm_models import NotificacionORM
from app.modules.notificaciones.infrastructure.persistence.mappers import to_domain, to_orm


class NotificacionRepositoryImpl(NotificacionRepository):
    def __init__(self, db: AsyncSession):
        self._db = db

    async def guardar(self, notificacion: Notificacion) -> Notificacion:
        res = await self._db.execute(
            select(NotificacionORM).where(NotificacionORM.id == notificacion.id)
        )
        orm = res.scalar_one_or_none()
        if orm:
            orm.leida = notificacion.leida
            orm.fecha_leida = notificacion.fecha_leida
            orm.titulo = notificacion.titulo
            orm.mensaje = notificacion.mensaje
            orm.datos = notificacion.datos
        else:
            orm = to_orm(notificacion)
            self._db.add(orm)
        await self._db.flush()
        return to_domain(orm)

    async def guardar_varias(self, notificaciones: list[Notificacion]) -> list[Notificacion]:
        orms = [to_orm(n) for n in notificaciones]
        self._db.add_all(orms)
        await self._db.flush()
        return [to_domain(orm) for orm in orms]

    async def obtener_por_id(self, notificacion_id: UUID) -> Notificacion | None:
        res = await self._db.execute(
            select(NotificacionORM).where(NotificacionORM.id == notificacion_id)
        )
        orm = res.scalar_one_or_none()
        return to_domain(orm) if orm else None

    async def listar_por_usuario(
        self,
        usuario_id: UUID,
        leida: bool | None = None,
        modulo: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[Sequence[Notificacion], int]:
        stmt = select(NotificacionORM).where(NotificacionORM.usuario_id == usuario_id)

        if leida is not None:
            stmt = stmt.where(NotificacionORM.leida == leida)
        if modulo:
            stmt = stmt.where(NotificacionORM.modulo == modulo)

        # Count total
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_res = await self._db.execute(count_stmt)
        total = total_res.scalar_one_or_none() or 0

        # Paginated query
        offset = (page - 1) * page_size
        stmt = stmt.order_by(NotificacionORM.created_at.desc()).offset(offset).limit(page_size)
        res = await self._db.execute(stmt)
        orms = res.scalars().all()

        return [to_domain(orm) for orm in orms], total

    async def contar_no_leidas(self, usuario_id: UUID) -> int:
        stmt = (
            select(func.count(NotificacionORM.id))
            .where(NotificacionORM.usuario_id == usuario_id, NotificacionORM.leida == False)
        )
        res = await self._db.execute(stmt)
        return res.scalar_one_or_none() or 0

    async def marcar_todas_como_leidas(self, usuario_id: UUID) -> int:
        now = datetime.now(timezone.utc)
        stmt = (
            update(NotificacionORM)
            .where(NotificacionORM.usuario_id == usuario_id, NotificacionORM.leida == False)
            .values(leida=True, fecha_leida=now)
        )
        res = await self._db.execute(stmt)
        await self._db.flush()
        return res.rowcount
