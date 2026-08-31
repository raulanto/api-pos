from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.modules.usuarios.application.ports.usuario_repository import UsuarioRepository
from app.modules.usuarios.domain.entities import Usuario, ROL_ADMIN
from app.modules.usuarios.infrastructure.persistence.orm_models import UsuarioORM, RolORM
from app.modules.usuarios.infrastructure.persistence.mappers import to_domain_usuario, to_orm_usuario
from app.shared.responses import Page, PageParams, Sort


class SqlAlchemyUsuarioRepository(UsuarioRepository):
    _ORDEN = {
        "nombre": UsuarioORM.nombre,
        "email": UsuarioORM.email,
        "created_at": UsuarioORM.created_at,
        "last_login_at": UsuarioORM.last_login_at,
    }

    def __init__(self, db: AsyncSession):
        self._db = db

    async def guardar(self, usuario: Usuario) -> None:
        orm = to_orm_usuario(usuario)
        await self._db.merge(orm)
        await self._db.flush()

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

    async def listar(
        self,
        paginacion: PageParams,
        orden: Sort,
        sucursal_id: UUID | None = None,
        incluir_inactivos: bool = True,
    ) -> Page:
        condiciones = []
        if sucursal_id is not None:
            condiciones.append(UsuarioORM.sucursal_id == sucursal_id)
        if not incluir_inactivos:
            condiciones.append(UsuarioORM.activo.is_(True))

        col = self._ORDEN.get(orden.field, UsuarioORM.nombre)
        orden_expr = col.desc() if orden.descending else col.asc()

        total = await self._db.scalar(
            select(func.count()).select_from(UsuarioORM).where(*condiciones)
        )
        filas = (await self._db.execute(
            select(UsuarioORM)
            .where(*condiciones)
            .order_by(orden_expr)
            .limit(paginacion.limit)
            .offset(paginacion.offset)
        )).scalars().all()
        return Page(items=[to_domain_usuario(o) for o in filas], total=int(total or 0))

    async def contar_admins_activos(self, excluir_usuario_id: UUID | None = None) -> int:
        stmt = (
            select(func.count(UsuarioORM.id))
            .join(RolORM, RolORM.id == UsuarioORM.rol_id)
            .where(RolORM.codigo == ROL_ADMIN, UsuarioORM.activo.is_(True))
        )
        if excluir_usuario_id is not None:
            stmt = stmt.where(UsuarioORM.id != excluir_usuario_id)
        return int((await self._db.execute(stmt)).scalar_one())
