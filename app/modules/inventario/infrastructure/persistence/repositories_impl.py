from uuid import UUID
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func, or_
from app.modules.inventario.application.ports.categoria_repository import CategoriaRepository
from app.modules.inventario.application.ports.producto_repository import ProductoRepository
from app.modules.inventario.application.ports.existencia_repository import ExistenciaRepository
from app.modules.inventario.application.ports.movimiento_repository import MovimientoRepository
from app.modules.inventario.application.dtos import (
    FiltroProductos, FiltroMovimientos, Paginacion, Pagina,
)
from app.modules.inventario.domain.entities import Categoria, Producto, Existencia, MovimientoInventario
from app.modules.inventario.infrastructure.persistence.orm_models import (
    CategoriaORM, ProductoORM, ExistenciaORM, MovimientoInventarioORM,
)
from app.modules.inventario.infrastructure.persistence.mappers import (
    to_domain_categoria, to_orm_categoria,
    to_domain_producto, to_orm_producto,
    to_domain_existencia, to_orm_existencia,
    to_domain_movimiento, to_orm_movimiento,
)

# Nota de transacción: los métodos de escritura hacen `flush` (no `commit`).
# El router es dueño de la transacción y hace un único `commit` al final del
# request; así una transferencia (2 movimientos) es atómica y los listeners de
# auditoría escriben en el mismo commit.


class SqlAlchemyCategoriaRepository(CategoriaRepository):
    def __init__(self, db: AsyncSession):
        self._db = db

    async def guardar(self, categoria: Categoria) -> None:
        self._db.add(to_orm_categoria(categoria))
        await self._db.flush()

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

    async def obtener_por_id(self, categoria_id: UUID) -> Categoria | None:
        orm = (await self._db.execute(
            select(CategoriaORM).where(CategoriaORM.id == categoria_id)
        )).scalar_one_or_none()
        return to_domain_categoria(orm) if orm else None

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

    async def tiene_productos_activos(self, categoria_id: UUID) -> bool:
        total = await self._db.scalar(
            select(func.count())
            .select_from(ProductoORM)
            .where(ProductoORM.categoria_id == categoria_id, ProductoORM.activo.is_(True))
        )
        return bool(total)


class SqlAlchemyProductoRepository(ProductoRepository):
    def __init__(self, db: AsyncSession):
        self._db = db

    async def guardar(self, producto: Producto) -> None:
        self._db.add(to_orm_producto(producto))
        await self._db.flush()

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

    async def obtener_por_id(self, producto_id: UUID) -> Producto | None:
        orm = (await self._db.execute(
            select(ProductoORM).where(ProductoORM.id == producto_id)
        )).scalar_one_or_none()
        return to_domain_producto(orm) if orm else None

    async def buscar_por_sku(self, sku: str, solo_activos: bool = True) -> Producto | None:
        stmt = select(ProductoORM).where(ProductoORM.sku == sku)
        if solo_activos:
            stmt = stmt.where(ProductoORM.activo.is_(True))
        orm = (await self._db.execute(stmt)).scalars().first()
        return to_domain_producto(orm) if orm else None

    async def buscar_por_codigo_barras(
        self, codigo_barras: str, solo_activos: bool = True
    ) -> Producto | None:
        stmt = select(ProductoORM).where(ProductoORM.codigo_barras == codigo_barras)
        if solo_activos:
            stmt = stmt.where(ProductoORM.activo.is_(True))
        orm = (await self._db.execute(stmt)).scalars().first()
        return to_domain_producto(orm) if orm else None

    async def listar(self, filtro: FiltroProductos, paginacion: Paginacion) -> Pagina:
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

        total = await self._db.scalar(
            select(func.count()).select_from(ProductoORM).where(*condiciones)
        )
        filas = (await self._db.execute(
            select(ProductoORM)
            .where(*condiciones)
            .order_by(ProductoORM.nombre)
            .limit(paginacion.limit)
            .offset(paginacion.offset)
        )).scalars().all()
        return Pagina(items=[to_domain_producto(o) for o in filas], total=int(total or 0))


class SqlAlchemyExistenciaRepository(ExistenciaRepository):
    def __init__(self, db: AsyncSession):
        self._db = db

    async def obtener(self, producto_id: UUID, sucursal_id: UUID) -> Existencia | None:
        orm = (await self._db.execute(
            select(ExistenciaORM).where(
                ExistenciaORM.producto_id == producto_id,
                ExistenciaORM.sucursal_id == sucursal_id,
            )
        )).scalar_one_or_none()
        return to_domain_existencia(orm) if orm else None

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

    async def crear(self, existencia: Existencia) -> None:
        self._db.add(to_orm_existencia(existencia))
        await self._db.flush()

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


class SqlAlchemyMovimientoRepository(MovimientoRepository):
    def __init__(self, db: AsyncSession):
        self._db = db

    async def guardar(self, movimiento: MovimientoInventario) -> None:
        self._db.add(to_orm_movimiento(movimiento))
        await self._db.flush()

    async def obtener_por_id(self, movimiento_id: UUID) -> MovimientoInventario | None:
        orm = (await self._db.execute(
            select(MovimientoInventarioORM).where(MovimientoInventarioORM.id == movimiento_id)
        )).scalar_one_or_none()
        return to_domain_movimiento(orm) if orm else None

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
