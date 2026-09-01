from uuid import UUID
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func
from sqlalchemy.orm import selectinload
from app.modules.inventario.application.ports.existencia_repository import ExistenciaRepository
from app.modules.inventario.application.dtos import FiltroExistencias
from app.modules.inventario.domain.entities import Existencia
from app.modules.inventario.infrastructure.persistence.orm_models import ExistenciaORM, ProductoORM
from app.modules.inventario.infrastructure.persistence.mappers import to_domain_existencia, to_orm_existencia
from app.shared.responses import Page, PageParams, Sort


_ORDEN_EXISTENCIA = {
    "cantidad": ExistenciaORM.cantidad,
    "stock_minimo": ExistenciaORM.stock_minimo,
    "updated_at": ExistenciaORM.updated_at,
}


"""
    Repositorio para la gestión de existencias.
    
    Implementa la interfaz ExistenciaRepository para operaciones CRUD.
    
"""
class SqlAlchemyExistenciaRepository(ExistenciaRepository):
    """
        Inicializa el repositorio.
        @params:
        - db: Sesión de base de datos.
        
        @returns:
        - None
    """
    def __init__(self, db: AsyncSession):
        self._db = db

    """
        Obtiene una existencia por ID.
        @params:
        - producto_id: ID del producto.
        - sucursal_id: ID de la sucursal.
        
        @returns:
        - Existencia | None
    """
    async def obtener(self, producto_id: UUID, sucursal_id: UUID) -> Existencia | None:
        orm = (await self._db.execute(
            select(ExistenciaORM).where(
                ExistenciaORM.producto_id == producto_id,
                ExistenciaORM.sucursal_id == sucursal_id,
            )
        )).scalar_one_or_none()
        return to_domain_existencia(orm) if orm else None

    async def buscar(
        self,
        filtro: FiltroExistencias,
        paginacion: PageParams,
        orden: Sort,
        includes: frozenset[str] = frozenset(),
    ) -> Page:
        condiciones = []
        if filtro.producto_id is not None:
            condiciones.append(ExistenciaORM.producto_id == filtro.producto_id)
        if filtro.sucursal_id is not None:
            condiciones.append(ExistenciaORM.sucursal_id == filtro.sucursal_id)

        base = select(ExistenciaORM).where(*condiciones)
        count_base = select(func.count()).select_from(ExistenciaORM).where(*condiciones)
        if filtro.solo_bajo_stock:
            base = base.join(ProductoORM, ProductoORM.id == ExistenciaORM.producto_id).where(
                ProductoORM.activo.is_(True),
                ExistenciaORM.cantidad <= ExistenciaORM.stock_minimo,
            )
            count_base = count_base.join(
                ProductoORM, ProductoORM.id == ExistenciaORM.producto_id
            ).where(
                ProductoORM.activo.is_(True),
                ExistenciaORM.cantidad <= ExistenciaORM.stock_minimo,
            )

        col = _ORDEN_EXISTENCIA.get(orden.field, ExistenciaORM.updated_at)
        orden_expr = col.desc() if orden.descending else col.asc()

        total = await self._db.scalar(count_base)
        opts = [selectinload(ExistenciaORM.producto)] if "producto" in includes else []
        filas = (await self._db.execute(
            base.options(*opts)
            .order_by(orden_expr)
            .limit(paginacion.limit)
            .offset(paginacion.offset)
        )).scalars().all()
        return Page(
            items=[to_domain_existencia(o, includes) for o in filas], total=int(total or 0)
        )

    """
        Actualiza la cantidad de una existencia.
        @params:
        - producto_id: ID del producto.
        - sucursal_id: ID de la sucursal.
        - nueva_cantidad: Nueva cantidad.
        
        @returns:
        - None
    """
    async def actualizar_cantidad(self, producto_id: UUID, sucursal_id: UUID, nueva_cantidad: Decimal) -> None:
        await self._db.execute(
            update(ExistenciaORM)
            .where(
                ExistenciaORM.producto_id == producto_id,
                ExistenciaORM.sucursal_id == sucursal_id,
            )
            .values(cantidad=nueva_cantidad)
        )
        await self._db.flush()

    """
        Crea una existencia.
        @params:
        - existencia: Existencia a crear.
        
        @returns:
        - None
    """
    async def crear(self, existencia: Existencia) -> None:
        self._db.add(to_orm_existencia(existencia))
        await self._db.flush()

    """
        Lista las existencias.
        @params:
        - producto_id: ID del producto.
        - sucursal_id: ID de la sucursal.
        
        @returns:
        - list[Existencia]
    """
    async def listar(
        self,
        producto_id: UUID | None = None,
        sucursal_id: UUID | None = None,
    ) -> list[Existencia]:
        stmt = select(ExistenciaORM)
        if producto_id is not None:
            stmt = stmt.where(ExistenciaORM.producto_id == producto_id)
        if sucursal_id is not None:
            stmt = stmt.where(ExistenciaORM.sucursal_id == sucursal_id)
        filas = (await self._db.execute(stmt)).scalars().all()
        return [to_domain_existencia(o) for o in filas]

    """
        Lista las existencias bajo stock.
        @params:
        - sucursal_id: ID de la sucursal.
        
        @returns:
        - list[Existencia]
    """
    async def listar_bajo_stock(self, sucursal_id: UUID | None = None) -> list[Existencia]:
        stmt = (
            select(ExistenciaORM)
            .join(ProductoORM, ProductoORM.id == ExistenciaORM.producto_id)
            .where(
                ProductoORM.activo.is_(True),
                ExistenciaORM.cantidad <= ExistenciaORM.stock_minimo,
            )
        )
        if sucursal_id is not None:
            stmt = stmt.where(ExistenciaORM.sucursal_id == sucursal_id)
        filas = (await self._db.execute(stmt)).scalars().all()
        return [to_domain_existencia(o) for o in filas]

    """
        Actualiza los umbrales de una existencia.
        @params:
        - producto_id: ID del producto.
        - sucursal_id: ID de la sucursal.
        - stock_minimo: Stock minimo.
        - stock_maximo: Stock maximo.
        
        @returns:
        - None
    """
    async def actualizar_umbrales(
        self,
        producto_id: UUID,
        sucursal_id: UUID,
        stock_minimo: Decimal,
        stock_maximo: Decimal | None,
    ) -> None:
        await self._db.execute(
            update(ExistenciaORM)
            .where(
                ExistenciaORM.producto_id == producto_id,
                ExistenciaORM.sucursal_id == sucursal_id,
            )
            .values(stock_minimo=stock_minimo, stock_maximo=stock_maximo)
        )
        await self._db.flush()
