from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func, or_
from app.modules.inventario.application.ports.producto_repository import ProductoRepository
from app.modules.inventario.application.dtos import FiltroProductos
from app.shared.responses import Page, PageParams, Sort
from app.modules.inventario.domain.entities import Producto
from app.modules.inventario.infrastructure.persistence.orm_models import ProductoORM
from app.modules.inventario.infrastructure.persistence.mappers import to_domain_producto, to_orm_producto

"""
Repositorio para la gestión de productos.

Implementa la interfaz ProductoRepository para operaciones CRUD.
"""
class SqlAlchemyProductoRepository(ProductoRepository):
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
        Funcion: Guarda un producto.
        @params:
        - producto: Producto a guardar.
        
        @returns:
        - None
    """
    async def guardar(self, producto: Producto) -> None:
        self._db.add(to_orm_producto(producto))
        await self._db.flush()

    """
        Funcion: Actualiza un producto.
        @params:
        - producto: Producto a actualizar.
        
        @returns:
        - None
    """
    async def actualizar(self, producto: Producto) -> None:
        await self._db.execute(
            update(ProductoORM)
            .where(ProductoORM.id == producto.id)
            .values(
                nombre=producto.nombre,
                descripcion=producto.descripcion,
                categoria_id=producto.categoria_id,
                unidad_medida=producto.unidad_medida,
                precio_venta=producto.precio_venta,
                costo=producto.costo,
                impuesto_tasa=producto.impuesto_tasa,
                permite_stock_negativo=producto.permite_stock_negativo,
                codigo_barras=producto.codigo_barras,
                activo=producto.activo,
            )
        )
        await self._db.flush()

    """
        Funcion: Obtiene un producto por ID.
        @params:
        - producto_id: ID del producto.
        
        @returns:
        - Producto | None
    """
    async def obtener_por_id(self, producto_id: UUID) -> Producto | None:
        orm = (await self._db.execute(
            select(ProductoORM).where(ProductoORM.id == producto_id)
        )).scalar_one_or_none()
        return to_domain_producto(orm) if orm else None
    
    """
        Funcion: Busca un producto por SKU.
        @params:
        - sku: SKU del producto.
        - solo_activos: Solo productos activos.
        
        @returns:
        - Producto | None
    """
    async def buscar_por_sku(self, sku: str, solo_activos: bool = True) -> Producto | None:
        stmt = select(ProductoORM).where(ProductoORM.sku == sku)
        if solo_activos:
            stmt = stmt.where(ProductoORM.activo.is_(True))
        orm = (await self._db.execute(stmt)).scalars().first()
        return to_domain_producto(orm) if orm else None

    """
        Funcion: Busca un producto por codigo de barras.
        @params:
        - codigo_barras: Codigo de barras del producto.
        - solo_activos: Solo productos activos.
        
        @returns:
        - Producto | None
    """
    async def buscar_por_codigo_barras(
        self, codigo_barras: str, solo_activos: bool = True
    ) -> Producto | None:
        stmt = select(ProductoORM).where(ProductoORM.codigo_barras == codigo_barras)
        if solo_activos:
            stmt = stmt.where(ProductoORM.activo.is_(True))
        orm = (await self._db.execute(stmt)).scalars().first()
        return to_domain_producto(orm) if orm else None

    """
        Funcion: Lista los productos.
        @params:
        - filtro: Filtros de búsqueda.
        - paginacion: Paginación.
        
        @returns:
        - Pagina
    """ 
    _ORDEN = {
        "nombre": ProductoORM.nombre,
        "sku": ProductoORM.sku,
        "precio_venta": ProductoORM.precio_venta,
        "created_at": ProductoORM.created_at,
    }

    async def listar(
        self, filtro: FiltroProductos, paginacion: PageParams, orden: Sort
    ) -> Page:
        condiciones = []
        if filtro.categoria_id is not None:
            condiciones.append(ProductoORM.categoria_id == filtro.categoria_id)
        if filtro.activo is not None:
            condiciones.append(ProductoORM.activo == filtro.activo)
        if filtro.busqueda:
            patron = f"%{filtro.busqueda.strip()}%"
            condiciones.append(or_(
                ProductoORM.nombre.ilike(patron),
                ProductoORM.sku.ilike(patron),
                ProductoORM.codigo_barras.ilike(patron),
            ))

        col = self._ORDEN.get(orden.field, ProductoORM.nombre)
        orden_expr = col.desc() if orden.descending else col.asc()

        total = await self._db.scalar(
            select(func.count()).select_from(ProductoORM).where(*condiciones)
        )
        filas = (await self._db.execute(
            select(ProductoORM)
            .where(*condiciones)
            .order_by(orden_expr)
            .limit(paginacion.limit)
            .offset(paginacion.offset)
        )).scalars().all()
        return Page(items=[to_domain_producto(o) for o in filas], total=int(total or 0))
