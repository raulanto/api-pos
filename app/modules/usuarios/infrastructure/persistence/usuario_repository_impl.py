from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.modules.usuarios.application.ports.usuario_repository import UsuarioRepository
from app.modules.usuarios.domain.entities import Usuario, ROL_ADMIN
from app.modules.usuarios.infrastructure.persistence.orm_models import UsuarioORM, RolORM
from app.modules.usuarios.infrastructure.persistence.mappers import to_domain_usuario, to_orm_usuario


class SqlAlchemyUsuarioRepository(UsuarioRepository):
    def __init__(self, db: AsyncSession):
        self._db = db

    async def guardar(self, usuario: Usuario) -> None:
        orm = to_orm_usuario(usuario)
        await self._db.merge(orm)
        await self._db.commit()

    async def obtener_por_id(self, usuario_id: UUID) -> Usuario | None:
        stmt = select(UsuarioORM).where(UsuarioORM.id == usuario_id)
        result = await self._db.execute(stmt)
        orm = result.scalar_one_or_none()
        return to_domain_usuario(orm) if orm else None

    async def obtener_por_email(self, email: str) -> Usuario | None:
        stmt = select(UsuarioORM).where(UsuarioORM.email == email)
        result = await self._db.execute(stmt)
        orm = result.scalar_one_or_none()
        return to_domain_usuario(orm) if orm else None

    async def listar(self, sucursal_id: UUID | None = None, incluir_inactivos: bool = True) -> list[Usuario]:
        stmt = select(UsuarioORM).order_by(UsuarioORM.nombre)
        if sucursal_id is not None:
            stmt = stmt.where(UsuarioORM.sucursal_id == sucursal_id)
        if not incluir_inactivos:
            stmt = stmt.where(UsuarioORM.activo.is_(True))
        result = await self._db.execute(stmt)
        return [to_domain_usuario(o) for o in result.scalars().all()]

    async def contar_admins_activos(self, excluir_usuario_id: UUID | None = None) -> int:
        stmt = (
            select(func.count(UsuarioORM.id))
            .join(RolORM, RolORM.id == UsuarioORM.rol_id)
            .where(RolORM.codigo == ROL_ADMIN, UsuarioORM.activo.is_(True))
        )
        if excluir_usuario_id is not None:
            stmt = stmt.where(UsuarioORM.id != excluir_usuario_id)
        return int((await self._db.execute(stmt)).scalar_one())
