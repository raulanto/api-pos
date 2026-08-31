from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func
from app.modules.inventario.application.ports.categoria_repository import CategoriaRepository
from app.modules.inventario.domain.entities import Categoria
from app.modules.inventario.infrastructure.persistence.orm_models import CategoriaORM, ProductoORM
from app.modules.inventario.infrastructure.persistence.mappers import to_domain_categoria, to_orm_categoria


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
    async def obtener_por_id(self, categoria_id: UUID) -> Categoria | None:
        orm = (await self._db.execute(
            select(CategoriaORM).where(CategoriaORM.id == categoria_id)
        )).scalar_one_or_none()
        return to_domain_categoria(orm) if orm else None

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
        activo: bool | None = None,
        categoria_padre_id: UUID | None = None,
    ) -> list[Categoria]:
        stmt = select(CategoriaORM)
        if activo is not None:
            stmt = stmt.where(CategoriaORM.activo == activo)
        if categoria_padre_id is not None:
            stmt = stmt.where(CategoriaORM.categoria_padre_id == categoria_padre_id)
        stmt = stmt.order_by(CategoriaORM.nombre)
        filas = (await self._db.execute(stmt)).scalars().all()
        return [to_domain_categoria(o) for o in filas]

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
