from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.modules.usuarios.application.ports.usuario_repository import UsuarioRepository
from app.modules.usuarios.domain.entities import Usuario
from app.modules.usuarios.infrastructure.persistence.orm_models import UsuarioORM
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
