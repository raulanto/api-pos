from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from sqlalchemy.exc import IntegrityError

from app.modules.inventario.domain.entities import Producto
from app.modules.inventario.application.ports.producto_repository import ProductoRepository
from app.modules.inventario.application.ports.categoria_repository import CategoriaRepository
from app.modules.inventario.domain.exceptions import (
    CategoriaNoEncontrada, SkuDuplicado, CodigoBarrasDuplicado,
)

@dataclass
class CrearProductoInput:
    sku: str
    nombre: str
    categoria_id: UUID
    unidad_medida: str
    precio_venta: Decimal
    costo: Decimal
    impuesto_tasa: Decimal
    permite_stock_negativo: bool = False
    codigo_barras: str | None = None
    descripcion: str | None = None

class CrearProductoUseCase:
    def __init__(self, producto_repo: ProductoRepository, categoria_repo: CategoriaRepository):
        self._producto_repo = producto_repo
        self._categoria_repo = categoria_repo

    async def ejecutar(self, data: CrearProductoInput) -> Producto:
        categoria = await self._categoria_repo.obtener_por_id(data.categoria_id)
        if not categoria:
            raise CategoriaNoEncontrada(f"No existe la categoría con id {data.categoria_id}")
        if not categoria.activo:
            raise CategoriaNoEncontrada(f"La categoría {data.categoria_id} está inactiva")

        # Chequeo amigable antes de tocar la BD (unicidad entre productos activos).
        if await self._producto_repo.buscar_por_sku(data.sku):
            raise SkuDuplicado(f"Ya existe un producto activo con el SKU '{data.sku}'")
        if data.codigo_barras and await self._producto_repo.buscar_por_codigo_barras(data.codigo_barras):
            raise CodigoBarrasDuplicado(
                f"Ya existe un producto activo con el código de barras '{data.codigo_barras}'"
            )

        producto = Producto.crear(
            sku=data.sku,
            nombre=data.nombre,
            categoria_id=data.categoria_id,
            unidad_medida=data.unidad_medida,
            precio_venta=data.precio_venta,
            costo=data.costo,
            impuesto_tasa=data.impuesto_tasa,
            permite_stock_negativo=data.permite_stock_negativo,
            codigo_barras=data.codigo_barras,
            descripcion=data.descripcion
        )
        try:
            await self._producto_repo.guardar(producto)
        except IntegrityError as e:
            # Red de seguridad ante carreras: la restricción de BD sigue mandando.
            raise _traducir_integridad(e, data.sku, data.codigo_barras)
        return producto


def _traducir_integridad(error: IntegrityError, sku: str, codigo_barras: str | None) -> Exception:
    detalle = str(getattr(error, "orig", error)).lower()
    if "codigo_barras" in detalle:
        return CodigoBarrasDuplicado(
            f"Ya existe un producto con el código de barras '{codigo_barras}'"
        )
    if "sku" in detalle:
        return SkuDuplicado(f"Ya existe un producto con el SKU '{sku}'")
    return SkuDuplicado("Violación de unicidad al crear el producto (SKU o código de barras)")
