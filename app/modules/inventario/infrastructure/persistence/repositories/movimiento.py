from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.modules.inventario.application.ports.movimiento_repository import MovimientoRepository
from app.modules.inventario.application.dtos import FiltroMovimientos, Paginacion, Pagina
from app.modules.inventario.domain.entities import MovimientoInventario
from app.modules.inventario.infrastructure.persistence.orm_models import MovimientoInventarioORM
from app.modules.inventario.infrastructure.persistence.mappers import to_domain_movimiento, to_orm_movimiento


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
    async def obtener_por_id(self, movimiento_id: UUID) -> MovimientoInventario | None:
        orm = (await self._db.execute(
            select(MovimientoInventarioORM).where(MovimientoInventarioORM.id == movimiento_id)
        )).scalar_one_or_none()
        return to_domain_movimiento(orm) if orm else None

    """
        Lista los movimientos.
        @params:
        - filtro: Filtros de búsqueda.
        - paginacion: Paginación.
        
        @returns:
        - Pagina
    """
    async def listar(self, filtro: FiltroMovimientos, paginacion: Paginacion) -> Pagina:
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

        total = await self._db.scalar(
            select(func.count()).select_from(MovimientoInventarioORM).where(*condiciones)
        )
        filas = (await self._db.execute(
            select(MovimientoInventarioORM)
            .where(*condiciones)
            .order_by(MovimientoInventarioORM.created_at.desc())
            .limit(paginacion.limit)
            .offset(paginacion.offset)
        )).scalars().all()
        return Pagina(items=[to_domain_movimiento(o) for o in filas], total=int(total or 0))
