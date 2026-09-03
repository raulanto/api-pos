from decimal import Decimal
from uuid import UUID

from sqlalchemy import select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.inventario.application.ports.componente_repository import (
    ProductoComponenteRepository,
)
from app.modules.inventario.domain.entities import ProductoComponente
from app.modules.inventario.infrastructure.persistence.orm_models import (
    ProductoComponenteORM, ProductoORM,
)
from app.modules.inventario.infrastructure.persistence.mappers import to_domain_componente

_PC = ProductoComponenteORM


class SqlAlchemyProductoComponenteRepository(ProductoComponenteRepository):
    def __init__(self, db: AsyncSession):
        self._db = db

    async def listar_por_kit(
        self, kit_id: UUID, includes: frozenset[str] = frozenset()
    ) -> list[ProductoComponente]:
        opts = [selectinload(_PC.producto)] if "producto" in includes else []
        filas = (await self._db.execute(
            select(_PC).options(*opts).where(_PC.producto_kit_id == kit_id)
        )).scalars().all()
        return [to_domain_componente(f, includes) for f in filas]

    async def obtener(
        self, kit_id: UUID, componente_id: UUID
    ) -> ProductoComponente | None:
        orm = (await self._db.execute(
            select(_PC).where(
                _PC.producto_kit_id == kit_id,
                _PC.producto_componente_id == componente_id,
            )
        )).scalar_one_or_none()
        return to_domain_componente(orm) if orm else None

    async def agregar(self, componente: ProductoComponente) -> None:
        self._db.add(_PC(
            producto_kit_id=componente.producto_kit_id,
            producto_componente_id=componente.producto_componente_id,
            cantidad=componente.cantidad,
        ))
        await self._db.flush()

    async def actualizar_cantidad(
        self, kit_id: UUID, componente_id: UUID, cantidad: Decimal
    ) -> None:
        await self._db.execute(
            update(_PC)
            .where(
                _PC.producto_kit_id == kit_id,
                _PC.producto_componente_id == componente_id,
            )
            .values(cantidad=cantidad)
        )
        await self._db.flush()

    async def quitar(self, kit_id: UUID, componente_id: UUID) -> None:
        await self._db.execute(
            delete(_PC).where(
                _PC.producto_kit_id == kit_id,
                _PC.producto_componente_id == componente_id,
            )
        )
        await self._db.flush()

    async def reemplazar(
        self, kit_id: UUID, componentes: list[ProductoComponente]
    ) -> None:
        await self._db.execute(delete(_PC).where(_PC.producto_kit_id == kit_id))
        for c in componentes:
            self._db.add(_PC(
                producto_kit_id=kit_id,
                producto_componente_id=c.producto_componente_id,
                cantidad=c.cantidad,
            ))
        await self._db.flush()

    async def contar_por_kit(self, kit_id: UUID) -> int:
        total = await self._db.scalar(
            select(func.count()).select_from(_PC).where(_PC.producto_kit_id == kit_id)
        )
        return int(total or 0)

    async def es_componente_de_kit_activo(self, producto_id: UUID) -> bool:
        total = await self._db.scalar(
            select(func.count())
            .select_from(_PC)
            .join(ProductoORM, ProductoORM.id == _PC.producto_kit_id)
            .where(
                _PC.producto_componente_id == producto_id,
                ProductoORM.activo.is_(True),
            )
        )
        return bool(total)
