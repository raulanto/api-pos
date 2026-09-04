from uuid import UUID

from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.inventario.application.ports.unidad_repository import (
    ProductoUnidadRepository,
)
from app.modules.inventario.domain.entities import ProductoUnidad
from app.modules.inventario.infrastructure.persistence.orm_models import ProductoUnidadORM
from app.modules.inventario.infrastructure.persistence.mappers import to_domain_unidad

_PU = ProductoUnidadORM


class SqlAlchemyProductoUnidadRepository(ProductoUnidadRepository):
    def __init__(self, db: AsyncSession):
        self._db = db

    async def listar_por_producto(
        self, producto_id: UUID, incluir_inactivas: bool = False
    ) -> list[ProductoUnidad]:
        stmt = select(_PU).where(_PU.producto_id == producto_id)
        if not incluir_inactivas:
            stmt = stmt.where(_PU.activo.is_(True))
        filas = (await self._db.execute(stmt.order_by(_PU.factor.asc()))).scalars().all()
        return [to_domain_unidad(f) for f in filas]

    async def obtener(self, unidad_id: UUID) -> ProductoUnidad | None:
        orm = await self._db.get(_PU, unidad_id)
        return to_domain_unidad(orm) if orm else None

    async def obtener_por_codigo_barras(self, codigo_barras: str) -> ProductoUnidad | None:
        orm = (await self._db.execute(
            select(_PU).where(
                _PU.codigo_barras == codigo_barras, _PU.activo.is_(True)
            )
        )).scalars().first()
        return to_domain_unidad(orm) if orm else None

    async def existe_nombre(self, producto_id: UUID, nombre: str) -> bool:
        total = await self._db.scalar(
            select(func.count()).select_from(_PU).where(
                _PU.producto_id == producto_id,
                func.lower(_PU.nombre) == nombre.strip().lower(),
                _PU.activo.is_(True),
            )
        )
        return bool(total)

    async def crear(self, unidad: ProductoUnidad) -> None:
        self._db.add(_PU(
            id=unidad.id,
            producto_id=unidad.producto_id,
            nombre=unidad.nombre,
            unidad_medida=unidad.unidad_medida,
            factor=unidad.factor,
            precio_venta=unidad.precio_venta,
            codigo_barras=unidad.codigo_barras,
            activo=unidad.activo,
        ))
        await self._db.flush()

    async def actualizar(self, unidad: ProductoUnidad) -> None:
        await self._db.execute(
            update(_PU)
            .where(_PU.id == unidad.id)
            .values(
                nombre=unidad.nombre,
                unidad_medida=unidad.unidad_medida,
                factor=unidad.factor,
                precio_venta=unidad.precio_venta,
                codigo_barras=unidad.codigo_barras,
                activo=unidad.activo,
            )
        )
        await self._db.flush()
