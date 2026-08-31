from uuid import UUID
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.usuarios.application.ports.refresh_token_repository import RefreshTokenRepository
from app.modules.usuarios.domain.entities import RefreshToken
from app.modules.usuarios.infrastructure.persistence.orm_models import RefreshTokenORM
from app.modules.usuarios.infrastructure.persistence.mappers import (
    to_domain_refresh_token, to_orm_refresh_token,
)


class SqlAlchemyRefreshTokenRepository(RefreshTokenRepository):
    def __init__(self, db: AsyncSession):
        self._db = db

    async def guardar(self, token: RefreshToken) -> None:
        self._db.add(to_orm_refresh_token(token))
        await self._db.commit()

    async def obtener_por_hash(self, token_hash: str) -> RefreshToken | None:
        stmt = select(RefreshTokenORM).where(RefreshTokenORM.token_hash == token_hash)
        orm = (await self._db.execute(stmt)).scalar_one_or_none()
        return to_domain_refresh_token(orm) if orm else None

    async def revocar(self, token_id: UUID) -> None:
        await self._db.execute(
            update(RefreshTokenORM).where(RefreshTokenORM.id == token_id).values(revocado=True)
        )
        await self._db.commit()

    async def revocar_todos_del_usuario(self, usuario_id: UUID) -> None:
        await self._db.execute(
            update(RefreshTokenORM)
            .where(RefreshTokenORM.usuario_id == usuario_id, RefreshTokenORM.revocado.is_(False))
            .values(revocado=True)
        )
        await self._db.commit()
