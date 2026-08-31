from uuid import UUID
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.modules.inventario.application.ports.categoria_repository import CategoriaRepository
from app.modules.inventario.application.ports.producto_repository import ProductoRepository
from app.modules.inventario.application.ports.existencia_repository import ExistenciaRepository
from app.modules.inventario.application.ports.movimiento_repository import MovimientoRepository
from app.modules.inventario.domain.entities import Categoria, Producto, Existencia, MovimientoInventario
from app.modules.inventario.infrastructure.persistence.orm_models import CategoriaORM, ProductoORM, ExistenciaORM
from app.modules.inventario.infrastructure.persistence.mappers import (
    to_domain_categoria, to_orm_categoria,
    to_domain_producto, to_orm_producto,
    to_domain_existencia, to_orm_existencia,
    to_orm_movimiento
)

class SqlAlchemyCategoriaRepository(CategoriaRepository):
    def __init__(self, db: AsyncSession):
        self._db = db

    async def guardar(self, categoria: Categoria) -> None:
        orm = to_orm_categoria(categoria)
        await self._db.merge(orm)
        await self._db.commit()

    async def obtener_por_id(self, categoria_id: UUID) -> Categoria | None:
        stmt = select(CategoriaORM).where(CategoriaORM.id == categoria_id)
        result = await self._db.execute(stmt)
        orm = result.scalar_one_or_none()
        return to_domain_categoria(orm) if orm else None

class SqlAlchemyProductoRepository(ProductoRepository):
    def __init__(self, db: AsyncSession):
        self._db = db

    async def guardar(self, producto: Producto) -> None:
        orm = to_orm_producto(producto)
        await self._db.merge(orm)
        await self._db.commit()

    async def obtener_por_id(self, producto_id: UUID) -> Producto | None:
        stmt = select(ProductoORM).where(ProductoORM.id == producto_id)
        result = await self._db.execute(stmt)
        orm = result.scalar_one_or_none()
        return to_domain_producto(orm) if orm else None

class SqlAlchemyExistenciaRepository(ExistenciaRepository):
    def __init__(self, db: AsyncSession):
        self._db = db

    async def obtener(self, producto_id: UUID, sucursal_id: UUID) -> Existencia | None:
        stmt = select(ExistenciaORM).where(
            ExistenciaORM.producto_id == producto_id,
            ExistenciaORM.sucursal_id == sucursal_id
        )
        result = await self._db.execute(stmt)
        orm = result.scalar_one_or_none()
        return to_domain_existencia(orm) if orm else None

    async def actualizar_cantidad(self, producto_id: UUID, sucursal_id: UUID, nueva_cantidad: Decimal) -> None:
        stmt = (
            update(ExistenciaORM)
            .where(
                ExistenciaORM.producto_id == producto_id,
                ExistenciaORM.sucursal_id == sucursal_id
            )
            .values(cantidad=nueva_cantidad)
        )
        await self._db.execute(stmt)
        await self._db.commit()

    async def crear(self, existencia: Existencia) -> None:
        orm = to_orm_existencia(existencia)
        self._db.add(orm)
        await self._db.commit()

class SqlAlchemyMovimientoRepository(MovimientoRepository):
    def __init__(self, db: AsyncSession):
        self._db = db

    async def guardar(self, movimiento: MovimientoInventario) -> None:
        orm = to_orm_movimiento(movimiento)
        self._db.add(orm)
        await self._db.commit()
