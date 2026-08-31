from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from sqlalchemy.exc import IntegrityError

from app.modules.inventario.domain.entities import Producto
from app.modules.inventario.domain.exceptions import (
    ProductoNoEncontrado, CategoriaNoEncontrada, SkuDuplicado, CodigoBarrasDuplicado,
    ProductoConStockActivo,
)
from app.modules.inventario.application.dtos import FiltroProductos
from app.modules.inventario.application.ports.producto_repository import ProductoRepository
from app.modules.inventario.application.ports.categoria_repository import CategoriaRepository
from app.modules.inventario.application.ports.existencia_repository import ExistenciaRepository
from app.modules.inventario.application.use_cases.crear_producto import _traducir_integridad
from app.shared.responses import Page, PageParams, Sort


class ListarProductosUseCase:
    def __init__(self, producto_repo: ProductoRepository):
        self._repo = producto_repo

    async def ejecutar(
        self, filtro: FiltroProductos, paginacion: PageParams, orden: Sort
    ) -> Page:
        return await self._repo.listar(filtro, paginacion, orden)


class ObtenerProductoUseCase:
    def __init__(self, producto_repo: ProductoRepository):
        self._repo = producto_repo

    async def ejecutar(self, producto_id: UUID) -> Producto:
        producto = await self._repo.obtener_por_id(producto_id)
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
    nombre: str | None = None
    descripcion: str | None = None
    categoria_id: UUID | None = None
    unidad_medida: str | None = None
    precio_venta: Decimal | None = None
    costo: Decimal | None = None
    impuesto_tasa: Decimal | None = None
    permite_stock_negativo: bool | None = None
    codigo_barras: str | None = None
    cambiar_codigo_barras: bool = False


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

        if data.cambiar_codigo_barras and data.codigo_barras:
            existente = await self._repo.buscar_por_codigo_barras(data.codigo_barras)
            if existente and existente.id != producto.id:
                raise CodigoBarrasDuplicado(
                    f"Ya existe un producto activo con el código de barras '{data.codigo_barras}'"
                )

        producto.actualizar(
            nombre=data.nombre,
            descripcion=data.descripcion,
            categoria_id=data.categoria_id,
            unidad_medida=data.unidad_medida,
            precio_venta=data.precio_venta,
            costo=data.costo,
            impuesto_tasa=data.impuesto_tasa,
            permite_stock_negativo=data.permite_stock_negativo,
            codigo_barras=data.codigo_barras,
            cambiar_codigo_barras=data.cambiar_codigo_barras,
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
