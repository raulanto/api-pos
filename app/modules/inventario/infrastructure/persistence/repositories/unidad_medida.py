from uuid import UUID

from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.inventario.application.ports.unidad_medida_repository import (
    UnidadMedidaRepository,
)
from app.modules.inventario.domain.entities import UnidadMedida
from app.modules.inventario.infrastructure.persistence.orm_models import (
    UnidadMedidaORM, ProductoORM, ProductoUnidadORM,
)
from app.modules.inventario.infrastructure.persistence.mappers import to_domain_unidad_medida

_UM = UnidadMedidaORM


class SqlAlchemyUnidadMedidaRepository(UnidadMedidaRepository):
    def __init__(self, db: AsyncSession):
        self._db = db

    async def listar(self, incluir_inactivas: bool = False) -> list[UnidadMedida]:
        stmt = select(_UM)
        if not incluir_inactivas:
            stmt = stmt.where(_UM.activo.is_(True))
        filas = (await self._db.execute(stmt.order_by(_UM.codigo.asc()))).scalars().all()
        return [to_domain_unidad_medida(f) for f in filas]

    async def obtener(self, unidad_id: UUID) -> UnidadMedida | None:
        orm = await self._db.get(_UM, unidad_id)
        return to_domain_unidad_medida(orm) if orm else None

    async def obtener_por_codigo(self, codigo: str) -> UnidadMedida | None:
        orm = (await self._db.execute(
            select(_UM).where(func.lower(_UM.codigo) == codigo.strip().lower())
        )).scalars().first()
        return to_domain_unidad_medida(orm) if orm else None

    async def crear(self, unidad: UnidadMedida) -> None:
        self._db.add(_UM(
            id=unidad.id,
            codigo=unidad.codigo,
            nombre=unidad.nombre,
            tipo_magnitud=unidad.tipo_magnitud.value,
            decimales=unidad.decimales,
            activo=unidad.activo,
        ))
        await self._db.flush()

    async def actualizar(self, unidad: UnidadMedida) -> None:
        await self._db.execute(
            update(_UM)
            .where(_UM.id == unidad.id)
            .values(
                nombre=unidad.nombre,
                tipo_magnitud=unidad.tipo_magnitud.value,
                decimales=unidad.decimales,
                activo=unidad.activo,
            )
        )
        await self._db.flush()

    async def esta_en_uso(self, unidad_id: UUID) -> bool:
        en_producto = await self._db.scalar(
            select(ProductoORM.id).where(
                ProductoORM.unidad_medida_id == unidad_id
            ).limit(1)
        )
        if en_producto is not None:
            return True
        en_presentacion = await self._db.scalar(
            select(ProductoUnidadORM.id).where(
                ProductoUnidadORM.unidad_medida_id == unidad_id
            ).limit(1)
        )
        return en_presentacion is not None
