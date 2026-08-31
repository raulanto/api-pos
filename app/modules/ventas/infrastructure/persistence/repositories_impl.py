from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.modules.ventas.application.ports.venta_repository import VentaRepository
from app.modules.ventas.application.ports.caja_repository import CajaTurnoRepository
from app.modules.ventas.domain.entities import Venta, CajaTurno
from app.modules.ventas.infrastructure.persistence.orm_models import VentaORM, CajaTurnoORM
from app.modules.ventas.infrastructure.persistence.mappers import to_domain_venta, to_orm_venta, to_domain_caja_turno

class SqlAlchemyVentaRepository(VentaRepository):
    def __init__(self, db: AsyncSession):
        self._db = db

    async def guardar(self, venta: Venta) -> None:
        orm = to_orm_venta(venta)
        self._db.add(orm)
        await self._db.commit()

    async def obtener_por_id(self, venta_id: UUID) -> Venta | None:
        stmt = select(VentaORM).options(
            selectinload(VentaORM.lineas),
            selectinload(VentaORM.pagos)
        ).where(VentaORM.id == venta_id)
        result = await self._db.execute(stmt)
        orm = result.scalar_one_or_none()
        return to_domain_venta(orm) if orm else None

class SqlAlchemyCajaTurnoRepository(CajaTurnoRepository):
    def __init__(self, db: AsyncSession):
        self._db = db

    async def obtener_por_id(self, turno_id: UUID) -> CajaTurno | None:
        stmt = select(CajaTurnoORM).where(CajaTurnoORM.id == turno_id)
        result = await self._db.execute(stmt)
        orm = result.scalar_one_or_none()
        return to_domain_caja_turno(orm) if orm else None
