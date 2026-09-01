from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func
from sqlalchemy.orm import selectinload
from app.modules.inventario.application.ports.categoria_repository import CategoriaRepository
from app.modules.inventario.application.dtos import FiltroCategorias
from app.modules.inventario.domain.entities import Categoria
from app.modules.inventario.infrastructure.persistence.orm_models import CategoriaORM, ProductoORM
from app.modules.inventario.infrastructure.persistence.mappers import to_domain_categoria, to_orm_categoria
from app.shared.responses import Page, PageParams, Sort


_ORDEN_CATEGORIA = {"nombre": CategoriaORM.nombre}


def _opts_categoria(includes: frozenset[str]):
    return [selectinload(CategoriaORM.padre)] if "padre" in includes else []


"""
    Repositorio para la gestión de categorías.
    
    Implementa la interfaz CategoriaRepository para operaciones CRUD.
    
"""
class SqlAlchemyCategoriaRepository(CategoriaRepository):
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
        Guarda una categoría.
        @params:
        - categoria: Categoría a guardar.
        
        @returns:
        - None
    """
    async def guardar(self, categoria: Categoria) -> None:
        self._db.add(to_orm_categoria(categoria))
        await self._db.flush()

    """
        Actualiza una categoría.
        @params:
        - categoria: Categoría a actualizar.
        
        @returns:
        - None
    """
    async def actualizar(self, categoria: Categoria) -> None:
        await self._db.execute(
            update(CategoriaORM)
            .where(CategoriaORM.id == categoria.id)
            .values(
                nombre=categoria.nombre,
                categoria_padre_id=categoria.categoria_padre_id,
                activo=categoria.activo,
            )
        )
        await self._db.flush()

    """
        Obtiene una categoría por ID.
        @params:
        - categoria_id: ID de la categoría.
        
        @returns:
        - Categoria | None
    """
    async def obtener_por_id(
        self, categoria_id: UUID, includes: frozenset[str] = frozenset()
    ) -> Categoria | None:
        orm = (await self._db.execute(
            select(CategoriaORM).options(*_opts_categoria(includes)).where(CategoriaORM.id == categoria_id)
        )).scalar_one_or_none()
        return to_domain_categoria(orm, includes) if orm else None

    """
        Lista las categorías.
        @params:
        - activo: Estado activo.
        - categoria_padre_id: ID de la categoría padre.
        
        @returns:
        - list[Categoria]
    """
    async def listar(
        self,
        filtro: FiltroCategorias,
        paginacion: PageParams,
        orden: Sort,
        includes: frozenset[str] = frozenset(),
    ) -> Page:
        condiciones = []
        if filtro.activo is not None:
            condiciones.append(CategoriaORM.activo == filtro.activo)
        if filtro.categoria_padre_id is not None:
            condiciones.append(CategoriaORM.categoria_padre_id == filtro.categoria_padre_id)
        if filtro.busqueda:
            condiciones.append(CategoriaORM.nombre.ilike(f"%{filtro.busqueda.strip()}%"))

        col = _ORDEN_CATEGORIA.get(orden.field, CategoriaORM.nombre)
        orden_expr = col.desc() if orden.descending else col.asc()

        total = await self._db.scalar(
            select(func.count()).select_from(CategoriaORM).where(*condiciones)
        )
        filas = (await self._db.execute(
            select(CategoriaORM)
            .options(*_opts_categoria(includes))
            .where(*condiciones)
            .order_by(orden_expr)
            .limit(paginacion.limit)
            .offset(paginacion.offset)
        )).scalars().all()
        return Page(
            items=[to_domain_categoria(o, includes) for o in filas], total=int(total or 0)
        )

    """
        Verifica si una categoría tiene productos activos.
        @params:
        - categoria_id: ID de la categoría.
        
        @returns:
        - bool
    """
    async def tiene_productos_activos(self, categoria_id: UUID) -> bool:
        total = await self._db.scalar(
            select(func.count())
            .select_from(ProductoORM)
            .where(ProductoORM.categoria_id == categoria_id, ProductoORM.activo.is_(True))
        )
        return bool(total)
