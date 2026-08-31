from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, insert, delete
from sqlalchemy.orm import selectinload

from app.modules.usuarios.application.ports.catalogos_repository import (
    RolRepository, SucursalRepository, PermisoRepository,
)
from app.modules.usuarios.domain.entities import Rol, Sucursal, Permiso
from app.modules.usuarios.infrastructure.persistence.orm_models import (
    RolORM, SucursalORM, PermisoORM, rol_permiso_table,
)
from app.modules.usuarios.infrastructure.persistence.mappers import (
    to_domain_rol, to_domain_sucursal, to_domain_permiso,
)


class SqlAlchemyRolRepository(RolRepository):
    def __init__(self, db: AsyncSession):
        self._db = db

    async def obtener_por_id(self, rol_id: UUID) -> Rol | None:
        stmt = select(RolORM).options(selectinload(RolORM.permisos)).where(RolORM.id == rol_id)
        orm = (await self._db.execute(stmt)).scalar_one_or_none()
        return to_domain_rol(orm) if orm else None

    async def obtener_por_codigo(self, codigo: str) -> Rol | None:
        stmt = select(RolORM).options(selectinload(RolORM.permisos)).where(RolORM.codigo == codigo)
        orm = (await self._db.execute(stmt)).scalar_one_or_none()
        return to_domain_rol(orm) if orm else None

    async def listar(self) -> list[Rol]:
        stmt = select(RolORM).options(selectinload(RolORM.permisos)).order_by(RolORM.nombre)
        return [to_domain_rol(o) for o in (await self._db.execute(stmt)).scalars().all()]

    async def crear(self, rol: Rol) -> Rol:
        orm = RolORM(id=rol.id, codigo=rol.codigo, nombre=rol.nombre, descripcion=rol.descripcion)
        self._db.add(orm)
        await self._db.flush()
        return rol

    async def actualizar_datos(self, rol_id: UUID, nombre: str, descripcion: str) -> None:
        orm = await self._db.get(RolORM, rol_id)
        if orm is not None:
            orm.nombre = nombre
            orm.descripcion = descripcion
            await self._db.flush()

    async def eliminar(self, rol_id: UUID) -> None:
        await self._db.execute(delete(rol_permiso_table).where(rol_permiso_table.c.rol_id == rol_id))
        await self._db.execute(delete(RolORM).where(RolORM.id == rol_id))
        await self._db.flush()

    async def tiene_usuarios(self, rol_id: UUID) -> bool:
        from app.modules.usuarios.infrastructure.persistence.orm_models import UsuarioORM
        stmt = select(func.count(UsuarioORM.id)).where(UsuarioORM.rol_id == rol_id)
        return int((await self._db.execute(stmt)).scalar_one()) > 0

    async def asignar_permisos(self, rol_id: UUID, permiso_ids: list[UUID]) -> None:
        existentes = set(
            (await self._db.execute(
                select(rol_permiso_table.c.permiso_id).where(rol_permiso_table.c.rol_id == rol_id)
            )).scalars().all()
        )
        nuevos = [pid for pid in permiso_ids if pid not in existentes]
        if nuevos:
            await self._db.execute(
                insert(rol_permiso_table),
                [{"rol_id": rol_id, "permiso_id": pid} for pid in nuevos],
            )
            await self._db.flush()

    async def quitar_permiso(self, rol_id: UUID, permiso_id: UUID) -> None:
        await self._db.execute(
            delete(rol_permiso_table).where(
                rol_permiso_table.c.rol_id == rol_id,
                rol_permiso_table.c.permiso_id == permiso_id,
            )
        )
        await self._db.flush()


class SqlAlchemyPermisoRepository(PermisoRepository):
    def __init__(self, db: AsyncSession):
        self._db = db

    async def listar(self) -> list[Permiso]:
        stmt = select(PermisoORM).order_by(PermisoORM.codigo)
        return [to_domain_permiso(o) for o in (await self._db.execute(stmt)).scalars().all()]

    async def obtener_por_id(self, permiso_id: UUID) -> Permiso | None:
        orm = await self._db.get(PermisoORM, permiso_id)
        return to_domain_permiso(orm) if orm else None

    async def existen_todos(self, permiso_ids: list[UUID]) -> bool:
        if not permiso_ids:
            return True
        stmt = select(func.count(PermisoORM.id)).where(PermisoORM.id.in_(permiso_ids))
        encontrados = int((await self._db.execute(stmt)).scalar_one())
        return encontrados == len(set(permiso_ids))


class SqlAlchemySucursalRepository(SucursalRepository):
    def __init__(self, db: AsyncSession):
        self._db = db

    async def obtener_por_id(self, sucursal_id: UUID) -> Sucursal | None:
        stmt = select(SucursalORM).where(SucursalORM.id == sucursal_id)
        orm = (await self._db.execute(stmt)).scalar_one_or_none()
        return to_domain_sucursal(orm) if orm else None
