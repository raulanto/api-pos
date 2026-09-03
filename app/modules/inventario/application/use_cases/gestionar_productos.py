from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from sqlalchemy.exc import IntegrityError

from app.modules.inventario.domain.entities import Producto
from app.modules.inventario.domain.exceptions import (
    ProductoNoEncontrado, CategoriaNoEncontrada, SkuDuplicado, CodigoBarrasDuplicado,
    ProductoConStockActivo,
)
from app.modules.inventario.application.dtos import FiltroProductos, ProductoKpis
from app.modules.inventario.application.ports.producto_repository import ProductoRepository
from app.modules.inventario.application.ports.categoria_repository import CategoriaRepository
from app.modules.inventario.application.ports.existencia_repository import ExistenciaRepository
from app.modules.inventario.application.use_cases.crear_producto import _traducir_integridad
from app.modules.inventario.domain.value_objects import TipoProducto
from app.shared.responses import Page, PageParams, Sort


class ListarProductosUseCase:
    def __init__(self, producto_repo: ProductoRepository):
        self._repo = producto_repo

    async def ejecutar(
        self,
        filtro: FiltroProductos,
        paginacion: PageParams,
        orden: Sort,
        includes: frozenset[str] = frozenset(),
    ) -> Page:
        return await self._repo.listar(filtro, paginacion, orden, includes)


class ProductoKpisUseCase:
    """Devuelve los KPIs del catálogo + valuación de stock para un filtro."""

    def __init__(self, producto_repo: ProductoRepository):
        self._repo = producto_repo

    async def ejecutar(self, filtro: FiltroProductos) -> ProductoKpis:
        return await self._repo.kpis(filtro)


class ObtenerProductoUseCase:
    def __init__(self, producto_repo: ProductoRepository):
        self._repo = producto_repo

    async def ejecutar(
        self, producto_id: UUID, includes: frozenset[str] = frozenset()
    ) -> Producto:
        producto = await self._repo.obtener_por_id(producto_id, includes)
        if not producto:
            raise ProductoNoEncontrado(f"No existe el producto {producto_id}")
        return producto


class BuscarProductoPorCodigoBarrasUseCase:
    def __init__(self, producto_repo: ProductoRepository):
        self._repo = producto_repo

    async def ejecutar(self, codigo_barras: str) -> Producto:
        producto = await self._repo.buscar_por_codigo_barras(codigo_barras)
        if not producto:
            raise ProductoNoEncontrado(
                f"No hay un producto activo con el código de barras '{codigo_barras}'"
            )
        return producto


@dataclass
class ActualizarProductoInput:
    producto_id: UUID
    sku: str | None = None
    nombre: str | None = None
    descripcion: str | None = None
    categoria_id: UUID | None = None
    unidad_medida: str | None = None
    precio_venta: Decimal | None = None
    costo: Decimal | None = None
    impuesto_tasa: Decimal | None = None
    tipo: TipoProducto | None = None
    permite_stock_negativo: bool | None = None
    codigo_barras: str | None = None
    cambiar_codigo_barras: bool = False
    cambiar_descripcion: bool = False


class ActualizarProductoUseCase:
    def __init__(self, producto_repo: ProductoRepository, categoria_repo: CategoriaRepository):
        self._repo = producto_repo
        self._categoria_repo = categoria_repo

    async def ejecutar(self, data: ActualizarProductoInput) -> Producto:
        producto = await self._repo.obtener_por_id(data.producto_id)
        if not producto:
            raise ProductoNoEncontrado(f"No existe el producto {data.producto_id}")

        if data.categoria_id is not None:
            categoria = await self._categoria_repo.obtener_por_id(data.categoria_id)
            if not categoria:
                raise CategoriaNoEncontrada(f"No existe la categoría con id {data.categoria_id}")

        if data.sku is not None and data.sku != producto.sku:
            existente = await self._repo.buscar_por_sku(data.sku)
            if existente and existente.id != producto.id:
                raise SkuDuplicado(
                    f"Ya existe un producto activo con el SKU '{data.sku}'"
                )

        if data.cambiar_codigo_barras and data.codigo_barras:
            existente = await self._repo.buscar_por_codigo_barras(data.codigo_barras)
            if existente and existente.id != producto.id:
                raise CodigoBarrasDuplicado(
                    f"Ya existe un producto activo con el código de barras '{data.codigo_barras}'"
                )

        producto.actualizar(
            sku=data.sku,
            nombre=data.nombre,
            descripcion=data.descripcion,
            categoria_id=data.categoria_id,
            unidad_medida=data.unidad_medida,
            precio_venta=data.precio_venta,
            costo=data.costo,
            impuesto_tasa=data.impuesto_tasa,
            tipo=data.tipo,
            permite_stock_negativo=data.permite_stock_negativo,
            codigo_barras=data.codigo_barras,
            cambiar_codigo_barras=data.cambiar_codigo_barras,
            cambiar_descripcion=data.cambiar_descripcion,
        )
        try:
            await self._repo.actualizar(producto)
        except IntegrityError as e:
            raise _traducir_integridad(e, producto.sku, producto.codigo_barras)
        return producto


class DesactivarProductoUseCase:
    def __init__(self, producto_repo: ProductoRepository, existencia_repo: ExistenciaRepository):
        self._repo = producto_repo
        self._existencia_repo = existencia_repo

    async def ejecutar(self, producto_id: UUID, confirmar_con_stock: bool = False) -> Producto:
        producto = await self._repo.obtener_por_id(producto_id)
        if not producto:
            raise ProductoNoEncontrado(f"No existe el producto {producto_id}")

        if not confirmar_con_stock:
            existencias = await self._existencia_repo.listar(producto_id=producto_id)
            if any(e.cantidad > 0 for e in existencias):
                raise ProductoConStockActivo(
                    "El producto tiene existencia > 0 en al menos una sucursal. "
                    "Enviá `confirmar_con_stock=true` para desactivarlo de todas formas."
                )

        producto.desactivar()
        await self._repo.actualizar(producto)
        return producto


class ReactivarProductoUseCase:
    """Contraparte de DesactivarProductoUseCase: vuelve a poner `activo = True`.

    El índice único parcial (WHERE activo) sobre sku / codigo_barras prohíbe dos
    productos activos con el mismo valor, así que se valida antes de reactivar
    (y se traduce el IntegrityError como red de seguridad ante carreras).
    """

    def __init__(self, producto_repo: ProductoRepository):
        self._repo = producto_repo

    async def ejecutar(self, producto_id: UUID) -> Producto:
        producto = await self._repo.obtener_por_id(producto_id)
        if not producto:
            raise ProductoNoEncontrado(f"No existe el producto {producto_id}")
        if producto.activo:
            return producto  # idempotente

        conflicto_sku = await self._repo.buscar_por_sku(producto.sku)
        if conflicto_sku and conflicto_sku.id != producto.id:
            raise SkuDuplicado(
                f"Ya existe un producto activo con el SKU '{producto.sku}'; "
                "no se puede reactivar este."
            )
        if producto.codigo_barras:
            conflicto_cb = await self._repo.buscar_por_codigo_barras(producto.codigo_barras)
            if conflicto_cb and conflicto_cb.id != producto.id:
                raise CodigoBarrasDuplicado(
                    f"Ya existe un producto activo con el código de barras "
                    f"'{producto.codigo_barras}'; no se puede reactivar este."
                )

        producto.activar()
        try:
            await self._repo.actualizar(producto)
        except IntegrityError as e:
            raise _traducir_integridad(e, producto.sku, producto.codigo_barras)
        return producto
