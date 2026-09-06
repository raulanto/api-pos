from uuid import UUID

from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.inventario.application.ports.imagen_repository import ImagenRepository
from app.modules.inventario.domain.entities import ProductoImagen
from app.modules.inventario.infrastructure.persistence.orm_models import ProductoImagenORM
from app.modules.inventario.infrastructure.persistence.mappers import to_domain_imagen

_PI = ProductoImagenORM


class SqlAlchemyImagenRepository(ImagenRepository):
    def __init__(self, db: AsyncSession):
        self._db = db

    async def listar_por_producto(self, producto_id: UUID) -> list[ProductoImagen]:
        filas = (await self._db.execute(
            select(_PI)
            .where(_PI.producto_id == producto_id)
            .order_by(_PI.orden.asc(), _PI.created_at.asc())
        )).scalars().all()
        return [to_domain_imagen(f) for f in filas]

    async def listar_por_unidad(self, producto_unidad_id: UUID) -> list[ProductoImagen]:
        filas = (await self._db.execute(
            select(_PI)
            .where(_PI.producto_unidad_id == producto_unidad_id)
            .order_by(_PI.orden.asc(), _PI.created_at.asc())
        )).scalars().all()
        return [to_domain_imagen(f) for f in filas]

    async def obtener(self, imagen_id: UUID) -> ProductoImagen | None:
        orm = await self._db.get(_PI, imagen_id)
        return to_domain_imagen(orm) if orm else None

    async def crear(self, imagen: ProductoImagen) -> None:
        self._db.add(_PI(
            id=imagen.id,
            producto_id=imagen.producto_id,
            producto_unidad_id=imagen.producto_unidad_id,
            # Invariante: imagen S3 => la columna `url` queda NULL (la pública se
            # deriva prefirmada al leer; `imagen.url` puede traer ese valor
            # transitorio y no debe persistirse).
            url=None if imagen.object_key else imagen.url,
            object_key=imagen.object_key,
            content_type=imagen.content_type,
            alt_texto=imagen.alt_texto,
            orden=imagen.orden,
            es_principal=imagen.es_principal,
        ))
        await self._db.flush()

    async def actualizar(self, imagen: ProductoImagen) -> None:
        await self._db.execute(
            update(_PI)
            .where(_PI.id == imagen.id)
            .values(
                url=None if imagen.object_key else imagen.url,
                object_key=imagen.object_key,
                content_type=imagen.content_type,
                alt_texto=imagen.alt_texto,
                orden=imagen.orden,
                es_principal=imagen.es_principal,
            )
        )
        await self._db.flush()

    async def eliminar(self, imagen_id: UUID) -> None:
        await self._db.execute(delete(_PI).where(_PI.id == imagen_id))
        await self._db.flush()

    async def desmarcar_principal(
        self, producto_id: UUID | None, producto_unidad_id: UUID | None,
        excepto_id: UUID | None = None,
    ) -> None:
        stmt = update(_PI).values(es_principal=False)
        if producto_id is not None:
            stmt = stmt.where(_PI.producto_id == producto_id)
        else:
            stmt = stmt.where(_PI.producto_unidad_id == producto_unidad_id)
        if excepto_id is not None:
            stmt = stmt.where(_PI.id != excepto_id)
        await self._db.execute(stmt)
        await self._db.flush()
