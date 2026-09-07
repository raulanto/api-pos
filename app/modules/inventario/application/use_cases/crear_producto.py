from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from sqlalchemy.exc import IntegrityError

from app.modules.inventario.domain.entities import Producto
from app.modules.inventario.domain.value_objects import TipoProducto
from app.modules.inventario.application.ports.producto_repository import ProductoRepository
from app.modules.inventario.application.ports.categoria_repository import CategoriaRepository
from app.modules.inventario.application.ports.unidad_medida_repository import (
    UnidadMedidaRepository,
)
from app.modules.inventario.domain.exceptions import (
    CategoriaNoEncontrada, SkuDuplicado, CodigoBarrasDuplicado, UnidadMedidaNoEncontrada,
    InstanciaConfigInvalida,
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
    tipo: TipoProducto = TipoProducto.SIMPLE
    unidad_medida_id: UUID | None = None
    permite_venta_fraccionada: bool = False
    incremento_minimo_venta: Decimal | None = None
    requiere_lote: bool = False
    rastrea_instancia_abierta: bool = False
    instancia_capacidad_default: Decimal | None = None
    precio_incluye_impuesto: bool = False
    precio_mayoreo: Decimal | None = None
    cantidad_minima_mayoreo: Decimal | None = None
    es_sobre_pedido: bool = False

class CrearProductoUseCase:
    def __init__(
        self,
        producto_repo: ProductoRepository,
        categoria_repo: CategoriaRepository,
        unidad_medida_repo: UnidadMedidaRepository | None = None,
    ):
        self._producto_repo = producto_repo
        self._categoria_repo = categoria_repo
        self._unidad_medida_repo = unidad_medida_repo

    async def ejecutar(self, data: CrearProductoInput) -> Producto:
        categoria = await self._categoria_repo.obtener_por_id(data.categoria_id)
        if not categoria:
            raise CategoriaNoEncontrada(f"No existe la categoría con id {data.categoria_id}")
        if not categoria.activo:
            raise CategoriaNoEncontrada(f"La categoría {data.categoria_id} está inactiva")

        if data.unidad_medida_id is not None and self._unidad_medida_repo is not None:
            unidad = await self._unidad_medida_repo.obtener(data.unidad_medida_id)
            if unidad is None or not unidad.activo:
                raise UnidadMedidaNoEncontrada(
                    f"No existe una unidad de medida activa con id {data.unidad_medida_id}"
                )

        # Chequeo amigable antes de tocar la BD (unicidad entre productos activos).
        if await self._producto_repo.buscar_por_sku(data.sku):
            raise SkuDuplicado(f"Ya existe un producto activo con el SKU '{data.sku}'")
        if data.codigo_barras and await self._producto_repo.buscar_por_codigo_barras(data.codigo_barras):
            raise CodigoBarrasDuplicado(
                f"Ya existe un producto activo con el código de barras '{data.codigo_barras}'"
            )

        if data.rastrea_instancia_abierta and not (
            data.instancia_capacidad_default and data.instancia_capacidad_default > 0
        ):
            raise InstanciaConfigInvalida(
                "`rastrea_instancia_abierta` requiere `instancia_capacidad_default` > 0 "
                "(capacidad para auto-abrir un envase al vender)."
            )
        _validar_mayoreo(data.precio_mayoreo, data.cantidad_minima_mayoreo)

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
            descripcion=data.descripcion,
            tipo=data.tipo,
            unidad_medida_id=data.unidad_medida_id,
            permite_venta_fraccionada=data.permite_venta_fraccionada,
            incremento_minimo_venta=data.incremento_minimo_venta,
            requiere_lote=data.requiere_lote,
            rastrea_instancia_abierta=data.rastrea_instancia_abierta,
            instancia_capacidad_default=data.instancia_capacidad_default,
            precio_incluye_impuesto=data.precio_incluye_impuesto,
            precio_mayoreo=data.precio_mayoreo,
            cantidad_minima_mayoreo=data.cantidad_minima_mayoreo,
            es_sobre_pedido=data.es_sobre_pedido,
        )
        try:
            await self._producto_repo.guardar(producto)
        except IntegrityError as e:
            # Red de seguridad ante carreras: la restricción de BD sigue mandando.
            raise _traducir_integridad(e, data.sku, data.codigo_barras)
        return producto


def _validar_mayoreo(precio_mayoreo, cantidad_minima) -> None:
    """`precio_mayoreo` y `cantidad_minima_mayoreo` van juntos y positivos, o ninguno."""
    if (precio_mayoreo is None) != (cantidad_minima is None):
        raise ValueError(
            "`precio_mayoreo` y `cantidad_minima_mayoreo` deben definirse juntos."
        )
    if precio_mayoreo is not None and (precio_mayoreo < 0 or cantidad_minima <= 0):
        raise ValueError(
            "`precio_mayoreo` no puede ser negativo y `cantidad_minima_mayoreo` debe ser > 0."
        )


def _traducir_integridad(error: IntegrityError, sku: str, codigo_barras: str | None) -> Exception:
    detalle = str(getattr(error, "orig", error)).lower()
    if "codigo_barras" in detalle:
        return CodigoBarrasDuplicado(
            f"Ya existe un producto con el código de barras '{codigo_barras}'"
        )
    if "sku" in detalle:
        return SkuDuplicado(f"Ya existe un producto con el SKU '{sku}'")
    return SkuDuplicado("Violación de unicidad al crear el producto (SKU o código de barras)")
