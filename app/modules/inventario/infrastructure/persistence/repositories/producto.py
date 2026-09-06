from decimal import Decimal
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func, or_
from sqlalchemy.orm import selectinload
from app.modules.inventario.application.ports.producto_repository import ProductoRepository
from app.modules.inventario.application.dtos import FiltroProductos, ProductoKpis
from app.modules.inventario.domain.value_objects import TipoProducto
from app.shared.responses import Page, PageParams, Sort
from app.modules.inventario.domain.entities import Producto
from app.modules.inventario.infrastructure.persistence.orm_models import (
    ProductoORM, ExistenciaORM, ProductoImagenORM, ProductoUnidadORM,
    ProductoComponenteORM, LoteORM, ExistenciaLoteORM,
)
from app.modules.inventario.infrastructure.persistence.mappers import to_domain_producto, to_orm_producto


def _condiciones_producto(filtro: FiltroProductos) -> list:
    """Cláusulas WHERE compartidas por `listar` y `kpis` (mismo criterio de filtrado)."""
    cond = []
    if filtro.categoria_id:
        cond.append(ProductoORM.categoria_id.in_(filtro.categoria_id))
    if filtro.activo is not None:
        cond.append(ProductoORM.activo == filtro.activo)
    if filtro.busqueda:
        patron = f"%{filtro.busqueda.strip()}%"
        cond.append(or_(
            ProductoORM.nombre.ilike(patron),
            ProductoORM.sku.ilike(patron),
            ProductoORM.codigo_barras.ilike(patron),
        ))
    if filtro.tipo is not None:
        cond.append(ProductoORM.tipo == filtro.tipo.value)
    if filtro.permite_stock_negativo is not None:
        cond.append(ProductoORM.permite_stock_negativo.is_(filtro.permite_stock_negativo))
    if filtro.con_codigo_barras is True:
        cond.append(ProductoORM.codigo_barras.isnot(None))
    elif filtro.con_codigo_barras is False:
        cond.append(ProductoORM.codigo_barras.is_(None))
    if filtro.precio_min is not None:
        cond.append(ProductoORM.precio_venta >= filtro.precio_min)
    if filtro.precio_max is not None:
        cond.append(ProductoORM.precio_venta <= filtro.precio_max)
    if filtro.costo_min is not None:
        cond.append(ProductoORM.costo >= filtro.costo_min)
    if filtro.costo_max is not None:
        cond.append(ProductoORM.costo <= filtro.costo_max)
    if filtro.sucursal_id:
        cond.append(
            select(ExistenciaORM.id)
            .where(
                ExistenciaORM.producto_id == ProductoORM.id,
                ExistenciaORM.sucursal_id.in_(filtro.sucursal_id),
            )
            .exists()
        )
    if filtro.solo_bajo_stock:
        sub = select(ExistenciaORM.id).where(
            ExistenciaORM.producto_id == ProductoORM.id,
            ExistenciaORM.cantidad <= ExistenciaORM.stock_minimo,
        )
        if filtro.sucursal_id:
            sub = sub.where(ExistenciaORM.sucursal_id.in_(filtro.sucursal_id))
        cond.append(sub.exists())
    return cond


def _opts_producto(includes: frozenset[str], sucursal_ids: list[UUID] | None = None):
    # `imagen_principal` es un campo estándar de la respuesta: se carga
    # siempre, sin depender de `?include=`.
    opts = [selectinload(ProductoORM.imagen_principal)]
    if "categoria" in includes:
        opts.append(selectinload(ProductoORM.categoria))
    if "existencias" in includes:
        rel = ProductoORM.existencias
        if sucursal_ids:
            # Coherencia con el filtro `?sucursal_id=`: el embed trae sólo esas.
            rel = rel.and_(ExistenciaORM.sucursal_id.in_(sucursal_ids))
        opts.append(selectinload(rel))
    if "componentes" in includes:
        opts.append(selectinload(ProductoORM.componentes))
    if "unidades" in includes:
        opts.append(selectinload(ProductoORM.unidades))
    if "imagenes" in includes:
        opts.append(selectinload(ProductoORM.imagenes))
    return opts

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
                sku=producto.sku,
                nombre=producto.nombre,
                descripcion=producto.descripcion,
                categoria_id=producto.categoria_id,
                unidad_medida=producto.unidad_medida,
                unidad_medida_id=producto.unidad_medida_id,
                precio_venta=producto.precio_venta,
                costo=producto.costo,
                impuesto_tasa=producto.impuesto_tasa,
                tipo=producto.tipo.value,
                permite_stock_negativo=producto.permite_stock_negativo,
                permite_venta_fraccionada=producto.permite_venta_fraccionada,
                incremento_minimo_venta=producto.incremento_minimo_venta,
                codigo_barras=producto.codigo_barras,
                activo=producto.activo,
            )
        )
        await self._db.flush()

    async def eliminar_fisico(self, producto_id: UUID) -> list[str]:
        # Subconsulta de las presentaciones del producto: sus imágenes también
        # se van. Se resuelve ANTES de borrar `producto_unidad`.
        unidades_sub = (
            select(ProductoUnidadORM.id)
            .where(ProductoUnidadORM.producto_id == producto_id)
            .scalar_subquery()
        )
        imagenes_dueno = or_(
            ProductoImagenORM.producto_id == producto_id,
            ProductoImagenORM.producto_unidad_id.in_(unidades_sub),
        )

        object_keys = (await self._db.execute(
            select(ProductoImagenORM.object_key)
            .where(ProductoImagenORM.object_key.isnot(None), imagenes_dueno)
        )).scalars().all()

        # Orden respetando las FK: hijos -> ... -> producto.
        await self._db.execute(delete(ProductoImagenORM).where(imagenes_dueno))
        # Solo la receta donde ESTE producto es el kit. Si es componente de otro
        # kit, el DELETE de `producto` de abajo choca la FK -> IntegrityError.
        await self._db.execute(
            delete(ProductoComponenteORM)
            .where(ProductoComponenteORM.producto_kit_id == producto_id)
        )
        await self._db.execute(
            delete(ExistenciaLoteORM).where(ExistenciaLoteORM.producto_id == producto_id)
        )
        await self._db.execute(delete(LoteORM).where(LoteORM.producto_id == producto_id))
        await self._db.execute(
            delete(ExistenciaORM).where(ExistenciaORM.producto_id == producto_id)
        )
        await self._db.execute(
            delete(ProductoUnidadORM).where(ProductoUnidadORM.producto_id == producto_id)
        )
        await self._db.execute(delete(ProductoORM).where(ProductoORM.id == producto_id))
        # Fuerza el SQL ahora: un IntegrityError por movimientos/ventas sale acá
        # (dentro del use case) y no recién en el commit del request.
        await self._db.flush()
        return list(object_keys)

    """
        Funcion: Obtiene un producto por ID.
        @params:
        - producto_id: ID del producto.
        
        @returns:
        - Producto | None
    """
    async def obtener_por_id(
        self, producto_id: UUID, includes: frozenset[str] = frozenset()
    ) -> Producto | None:
        orm = (await self._db.execute(
            select(ProductoORM).options(*_opts_producto(includes)).where(ProductoORM.id == producto_id)
        )).scalar_one_or_none()
        return to_domain_producto(orm, includes) if orm else None
    
    """
        Funcion: Busca un producto por SKU.
        @params:
        - sku: SKU del producto.
        - solo_activos: Solo productos activos.
        
        @returns:
        - Producto | None
    """
    async def buscar_por_sku(self, sku: str, solo_activos: bool = True) -> Producto | None:
        stmt = select(ProductoORM).options(*_opts_producto(frozenset())).where(
            ProductoORM.sku == sku
        )
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
        stmt = select(ProductoORM).options(*_opts_producto(frozenset())).where(
            ProductoORM.codigo_barras == codigo_barras
        )
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
        self,
        filtro: FiltroProductos,
        paginacion: PageParams,
        orden: Sort,
        includes: frozenset[str] = frozenset(),
    ) -> Page:
        condiciones = _condiciones_producto(filtro)

        col = self._ORDEN.get(orden.field, ProductoORM.nombre)
        orden_expr = col.desc() if orden.descending else col.asc()

        total = await self._db.scalar(
            select(func.count()).select_from(ProductoORM).where(*condiciones)
        )
        filas = (await self._db.execute(
            select(ProductoORM)
            .options(*_opts_producto(includes, filtro.sucursal_id))
            .where(*condiciones)
            .order_by(orden_expr)
            .limit(paginacion.limit)
            .offset(paginacion.offset)
        )).scalars().all()
        return Page(
            items=[to_domain_producto(o, includes) for o in filas], total=int(total or 0)
        )

    async def kpis(self, filtro: FiltroProductos) -> ProductoKpis:
        cond = _condiciones_producto(filtro)
        P = ProductoORM

        # --- Agregados sobre el catálogo (tabla producto) ---
        c = (await self._db.execute(
            select(
                func.count(),
                func.count().filter(P.activo.is_(True)),
                func.count().filter(P.codigo_barras.isnot(None)),
                func.count(func.distinct(P.categoria_id)),
                func.min(P.precio_venta), func.max(P.precio_venta), func.avg(P.precio_venta),
                func.min(P.costo), func.max(P.costo), func.avg(P.costo),
                func.avg(P.precio_venta - P.costo),
            ).select_from(P).where(*cond)
        )).one()

        total = int(c[0] or 0)
        activos = int(c[1] or 0)
        con_cb = int(c[2] or 0)

        # Conteo por tipo (robusto ante cualquier valor del enum TipoProducto).
        filas_tipo = (await self._db.execute(
            select(P.tipo, func.count()).select_from(P).where(*cond).group_by(P.tipo)
        )).all()
        por_tipo = {t.value: 0 for t in TipoProducto}
        for tipo_val, n in filas_tipo:
            por_tipo[tipo_val] = int(n or 0)

        # --- Valuación de stock (tabla existencia), acotada a esos productos y sucursales ---
        ids_sub = select(P.id).where(*cond).scalar_subquery()
        ex_cond = [ExistenciaORM.producto_id.in_(ids_sub)]
        if filtro.sucursal_id:
            ex_cond.append(ExistenciaORM.sucursal_id.in_(filtro.sucursal_id))
        e = (await self._db.execute(
            select(
                func.coalesce(func.sum(ExistenciaORM.cantidad), 0),
                func.coalesce(func.sum(ExistenciaORM.cantidad * P.costo), 0),
                func.coalesce(func.sum(ExistenciaORM.cantidad * P.precio_venta), 0),
                func.count(func.distinct(ExistenciaORM.producto_id)),
                func.count(func.distinct(ExistenciaORM.producto_id)).filter(
                    ExistenciaORM.cantidad <= ExistenciaORM.stock_minimo
                ),
            )
            .select_from(ExistenciaORM)
            .join(P, P.id == ExistenciaORM.producto_id)
            .where(*ex_cond)
        )).one()

        con_existencia = int(e[3] or 0)

        def d2(v) -> Decimal | None:
            return round(Decimal(str(v)), 2) if v is not None else None

        return ProductoKpis(
            total=total,
            activos=activos,
            inactivos=total - activos,
            por_tipo=por_tipo,
            con_codigo_barras=con_cb,
            sin_codigo_barras=total - con_cb,
            categorias_distintas=int(c[3] or 0),
            precio_venta_min=d2(c[4]),
            precio_venta_max=d2(c[5]),
            precio_venta_promedio=d2(c[6]),
            costo_min=d2(c[7]),
            costo_max=d2(c[8]),
            costo_promedio=d2(c[9]),
            margen_promedio=d2(c[10]),
            unidades_en_stock=d2(e[0]) or Decimal("0.00"),
            valor_inventario_costo=d2(e[1]) or Decimal("0.00"),
            valor_inventario_venta=d2(e[2]) or Decimal("0.00"),
            productos_con_existencia=con_existencia,
            productos_sin_existencia=total - con_existencia,
            bajo_stock=int(e[4] or 0),
        )
