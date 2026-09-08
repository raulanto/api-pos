from uuid import UUID

from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.promociones.application.ports.cupon_repository import CuponRepository
from app.modules.promociones.domain.entities import Cupon, CuponUso
from app.modules.promociones.infrastructure.persistence.orm_models import (
    CuponORM, CuponUsoORM,
)
from app.modules.promociones.infrastructure.persistence.mappers import (
    to_domain_cupon, to_orm_cupon, to_orm_cupon_uso,
)


class SqlAlchemyCuponRepository(CuponRepository):
    def __init__(self, db: AsyncSession):
        self._db = db

    async def obtener_por_codigo(
        self, codigo: str, para_actualizar: bool = False,
    ) -> Cupon | None:
        stmt = select(CuponORM).where(CuponORM.codigo == (codigo or "").strip().upper())
        if para_actualizar:
            stmt = stmt.with_for_update()
        orm = (await self._db.execute(stmt)).scalar_one_or_none()
        return to_domain_cupon(orm) if orm else None

    async def listar_por_promocion(self, promocion_id: UUID) -> list[Cupon]:
        filas = (await self._db.execute(
            select(CuponORM).where(CuponORM.promocion_id == promocion_id)
            .order_by(CuponORM.created_at.desc())
        )).scalars().all()
        return [to_domain_cupon(o) for o in filas]

    async def crear(self, cupon: Cupon) -> None:
        self._db.add(to_orm_cupon(cupon))
        await self._db.flush()

    async def actualizar(self, cupon: Cupon) -> None:
        await self._db.execute(
            update(CuponORM).where(CuponORM.id == cupon.id).values(
                activo=cupon.activo, vigente_desde=cupon.vigente_desde,
                vigente_hasta=cupon.vigente_hasta, max_usos_total=cupon.max_usos_total,
                max_usos_por_persona=cupon.max_usos_por_persona,
            )
        )
        await self._db.flush()

    async def contar_usos(self, cupon_id: UUID) -> int:
        return int(await self._db.scalar(
            select(func.count()).select_from(CuponUsoORM)
            .where(CuponUsoORM.cupon_id == cupon_id)
        ) or 0)

    async def contar_usos_persona(
        self, cupon_id: UUID, telefono: str | None, cliente_id: UUID | None,
    ) -> int:
        cond = [CuponUsoORM.cupon_id == cupon_id]
        if cliente_id is not None:
            cond.append(CuponUsoORM.cliente_id == cliente_id)
        elif telefono is not None:
            cond.append(CuponUsoORM.telefono == telefono.strip())
        else:
            return 0
        return int(await self._db.scalar(
            select(func.count()).select_from(CuponUsoORM).where(*cond)
        ) or 0)

    async def registrar_uso(self, uso: CuponUso) -> None:
        self._db.add(to_orm_cupon_uso(uso))
        await self._db.flush()

    async def borrar_usos_de_venta(self, venta_id: UUID) -> None:
        await self._db.execute(
            CuponUsoORM.__table__.delete().where(CuponUsoORM.venta_id == venta_id)
        )
        await self._db.flush()
