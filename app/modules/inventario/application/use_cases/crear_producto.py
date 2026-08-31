from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID
from app.modules.inventario.domain.entities import Producto
from app.modules.inventario.application.ports.producto_repository import ProductoRepository
from app.modules.inventario.application.ports.categoria_repository import CategoriaRepository
from app.modules.inventario.domain.exceptions import CategoriaNoEncontrada

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
        await self._producto_repo.guardar(producto)
        return producto
