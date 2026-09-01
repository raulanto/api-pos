from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from app.modules.inventario.application.ports.movimiento_repository import MovimientoRepository
from app.modules.inventario.application.dtos import FiltroMovimientos
from app.shared.responses import Page, PageParams, Sort
from app.modules.inventario.domain.entities import MovimientoInventario
from app.modules.inventario.infrastructure.persistence.orm_models import MovimientoInventarioORM
from app.modules.inventario.infrastructure.persistence.mappers import to_domain_movimiento, to_orm_movimiento


def _opts_mov(includes: frozenset[str]):
    opts = []
    if "producto" in includes:
        opts.append(selectinload(MovimientoInventarioORM.producto))
    if "usuario" in includes:
        opts.append(selectinload(MovimientoInventarioORM.usuario))
    return opts


"""
    Repositorio para la gestión de movimientos.
    
    Implementa la interfaz MovimientoRepository para operaciones CRUD.
    
"""
class SqlAlchemyMovimientoRepository(MovimientoRepository):
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
        Guarda un movimiento.
        @params:
        - movimiento: Movimiento a guardar.
        
        @returns:
        - None
    """
    async def guardar(self, movimiento: MovimientoInventario) -> None:
        self._db.add(to_orm_movimiento(movimiento))
        await self._db.flush()

    """
        Obtiene un movimiento por ID.
        @params:
        - movimiento_id: ID del movimiento.
        
        @returns:
        - MovimientoInventario | None
    """
    async def obtener_por_id(
        self, movimiento_id: UUID, includes: frozenset[str] = frozenset()
    ) -> MovimientoInventario | None:
        orm = (await self._db.execute(
            select(MovimientoInventarioORM)
            .options(*_opts_mov(includes))
            .where(MovimientoInventarioORM.id == movimiento_id)
        )).scalar_one_or_none()
        return to_domain_movimiento(orm, includes) if orm else None

    """
        Lista los movimientos.
        @params:
        - filtro: Filtros de búsqueda.
        - paginacion: Paginación.
        
        @returns:
        - Pagina
    """
    _ORDEN = {
        "created_at": MovimientoInventarioORM.created_at,
        "cantidad": MovimientoInventarioORM.cantidad,
    }

    async def listar(
        self,
        filtro: FiltroMovimientos,
        paginacion: PageParams,
        orden: Sort,
        includes: frozenset[str] = frozenset(),
    ) -> Page:
        condiciones = []
        if filtro.producto_id is not None:
            condiciones.append(MovimientoInventarioORM.producto_id == filtro.producto_id)
        if filtro.sucursal_id is not None:
            condiciones.append(MovimientoInventarioORM.sucursal_id == filtro.sucursal_id)
        if filtro.tipo is not None:
            condiciones.append(MovimientoInventarioORM.tipo == filtro.tipo.value)
        if filtro.desde is not None:
            condiciones.append(MovimientoInventarioORM.created_at >= filtro.desde)
        if filtro.hasta is not None:
            condiciones.append(MovimientoInventarioORM.created_at <= filtro.hasta)

        col = self._ORDEN.get(orden.field, MovimientoInventarioORM.created_at)
        orden_expr = col.desc() if orden.descending else col.asc()

        total = await self._db.scalar(
            select(func.count()).select_from(MovimientoInventarioORM).where(*condiciones)
        )
        filas = (await self._db.execute(
            select(MovimientoInventarioORM)
            .options(*_opts_mov(includes))
            .where(*condiciones)
            .order_by(orden_expr)
            .limit(paginacion.limit)
            .offset(paginacion.offset)
        )).scalars().all()
        return Page(
            items=[to_domain_movimiento(o, includes) for o in filas], total=int(total or 0)
        )
