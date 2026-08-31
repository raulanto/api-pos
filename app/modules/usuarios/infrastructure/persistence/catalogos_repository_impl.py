from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.modules.usuarios.application.ports.catalogos_repository import RolRepository, SucursalRepository
from app.modules.usuarios.domain.entities import Rol, Sucursal
from app.modules.usuarios.infrastructure.persistence.orm_models import RolORM, SucursalORM
from app.modules.usuarios.infrastructure.persistence.mappers import to_domain_rol, to_domain_sucursal

class SqlAlchemyRolRepository(RolRepository):
    def __init__(self, db: AsyncSession):
        self._db = db

    async def obtener_por_id(self, rol_id: UUID) -> Rol | None:
        stmt = select(RolORM).options(selectinload(RolORM.permisos)).where(RolORM.id == rol_id)
        result = await self._db.execute(stmt)
        orm = result.scalar_one_or_none()
        return to_domain_rol(orm) if orm else None

class SqlAlchemySucursalRepository(SucursalRepository):
    def __init__(self, db: AsyncSession):
        self._db = db

    async def obtener_por_id(self, sucursal_id: UUID) -> Sucursal | None:
        stmt = select(SucursalORM).where(SucursalORM.id == sucursal_id)
        result = await self._db.execute(stmt)
        orm = result.scalar_one_or_none()
        return to_domain_sucursal(orm) if orm else None
