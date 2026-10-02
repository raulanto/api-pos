from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func
from app.modules.inventario.application.ports.marca_repository import MarcaRepository
from app.modules.inventario.application.dtos import FiltroMarcas
from app.modules.inventario.domain.entities import Marca
from app.modules.inventario.infrastructure.persistence.orm_models import MarcaORM, ProductoORM
from app.modules.inventario.infrastructure.persistence.mappers import to_domain_marca, to_orm_marca
from app.shared.responses import Page, PageParams, Sort


_ORDEN_MARCA = {"nombre": MarcaORM.nombre}


"""
    Repositorio para la gestión de marcas.
    
    Implementa la interfaz MarcaRepository para operaciones CRUD.
"""
class SqlAlchemyMarcaRepository(MarcaRepository):
    def __init__(self, db: AsyncSession):
        self._db = db
    
    async def guardar(self, marca: Marca) -> None:
        self._db.add(to_orm_marca(marca))
        await self._db.flush()

    async def actualizar(self, marca: Marca) -> None:
        await self._db.execute(
            update(MarcaORM)
            .where(MarcaORM.id == marca.id)
            .values(
                nombre=marca.nombre,
                activo=marca.activo,
            )
        )
        await self._db.flush()

    async def obtener_por_id(self, marca_id: UUID) -> Marca | None:
        orm = (await self._db.execute(
            select(MarcaORM).where(MarcaORM.id == marca_id)
        )).scalar_one_or_none()
        return to_domain_marca(orm) if orm else None

    async def listar(
        self,
        filtro: FiltroMarcas,
        paginacion: PageParams,
        orden: Sort,
    ) -> Page:
        condiciones = []
        if filtro.activo is not None:
            condiciones.append(MarcaORM.activo == filtro.activo)
        if filtro.busqueda:
            condiciones.append(MarcaORM.nombre.ilike(f"%{filtro.busqueda.strip()}%"))

        col = _ORDEN_MARCA.get(orden.field, MarcaORM.nombre)
        orden_expr = col.desc() if orden.descending else col.asc()

        total = await self._db.scalar(
            select(func.count()).select_from(MarcaORM).where(*condiciones)
        )
        filas = (await self._db.execute(
            select(MarcaORM)
            .where(*condiciones)
            .order_by(orden_expr)
            .limit(paginacion.limit)
            .offset(paginacion.offset)
        )).scalars().all()
        return Page(
            items=[to_domain_marca(o) for o in filas], total=int(total or 0)
        )

    async def tiene_productos_activos(self, marca_id: UUID) -> bool:
        total = await self._db.scalar(
            select(func.count())
            .select_from(ProductoORM)
            .where(ProductoORM.marca_id == marca_id, ProductoORM.activo.is_(True))
        )
        return bool(total)

    async def eliminar(self, marca_id: UUID) -> None:
        from sqlalchemy import delete
        await self._db.execute(
            delete(MarcaORM).where(MarcaORM.id == marca_id)
        )
        await self._db.flush()

