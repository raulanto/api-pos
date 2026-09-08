from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from sqlalchemy.exc import IntegrityError

from app.modules.inventario.domain.entities import Producto
from app.modules.inventario.domain.exceptions import (
    ProductoNoEncontrado, CategoriaNoEncontrada, SkuDuplicado, CodigoBarrasDuplicado,
    ProductoConStockActivo, ProductoConHistorial, KitInvalido, ProductoEsComponenteDeKit,
    UnidadMedidaNoEncontrada, LoteInvalido, InstanciaConfigInvalida,
)
from app.modules.inventario.application.ports.unidad_medida_repository import (
    UnidadMedidaRepository,
)
from app.modules.inventario.application.dtos import FiltroProductos, ProductoKpis
from app.modules.inventario.application.ports.producto_repository import ProductoRepository
from app.modules.inventario.application.ports.categoria_repository import CategoriaRepository
from app.modules.inventario.application.ports.existencia_repository import ExistenciaRepository
from app.modules.inventario.application.ports.componente_repository import (
    ProductoComponenteRepository,
)
from app.modules.inventario.application.ports.unidad_repository import (
    ProductoUnidadRepository,
)
from app.modules.inventario.application.ports.movimiento_repository import MovimientoRepository
from app.modules.inventario.application.ports.almacen_imagenes import AlmacenImagenes
from app.modules.inventario.application.use_cases.crear_producto import (
    _traducir_integridad, _validar_mayoreo,
)
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
    unidad_medida_id: UUID | None = None
    cambiar_unidad_medida_id: bool = False
    precio_venta: Decimal | None = None
    costo: Decimal | None = None
    impuesto_tasa: Decimal | None = None
    tipo: TipoProducto | None = None
    permite_stock_negativo: bool | None = None
    permite_venta_fraccionada: bool | None = None
    incremento_minimo_venta: Decimal | None = None
    cambiar_incremento_minimo_venta: bool = False
    requiere_lote: bool | None = None
    rastrea_instancia_abierta: bool | None = None
    instancia_capacidad_default: Decimal | None = None
    cambiar_instancia_capacidad_default: bool = False
    precio_incluye_impuesto: bool | None = None
    es_sobre_pedido: bool | None = None
    precio_mayoreo: Decimal | None = None
    cantidad_minima_mayoreo: Decimal | None = None
    cambiar_mayoreo: bool = False
    monedero_pct: Decimal | None = None
    monedero_monto: Decimal | None = None
    cambiar_monedero: bool = False
    codigo_barras: str | None = None
    cambiar_codigo_barras: bool = False
    cambiar_descripcion: bool = False


class ActualizarProductoUseCase:
    def __init__(
        self,
        producto_repo: ProductoRepository,
        categoria_repo: CategoriaRepository,
        componente_repo: ProductoComponenteRepository,
        unidad_repo: ProductoUnidadRepository,
        unidad_medida_repo: UnidadMedidaRepository | None = None,
        existencia_repo=None,
    ):
        self._repo = producto_repo
        self._categoria_repo = categoria_repo
        self._componente_repo = componente_repo
        self._unidad_repo = unidad_repo
        self._unidad_medida_repo = unidad_medida_repo
        self._existencia_repo = existencia_repo

    async def ejecutar(self, data: ActualizarProductoInput) -> Producto:
        producto = await self._repo.obtener_por_id(data.producto_id)
        if not producto:
            raise ProductoNoEncontrado(f"No existe el producto {data.producto_id}")

        if data.categoria_id is not None:
            categoria = await self._categoria_repo.obtener_por_id(data.categoria_id)
            if not categoria:
                raise CategoriaNoEncontrada(f"No existe la categoría con id {data.categoria_id}")

        if data.unidad_medida_id is not None and self._unidad_medida_repo is not None:
            unidad = await self._unidad_medida_repo.obtener(data.unidad_medida_id)
            if unidad is None or not unidad.activo:
                raise UnidadMedidaNoEncontrada(
                    f"No existe una unidad de medida activa con id {data.unidad_medida_id}"
                )

        if (
            data.tipo is not None
            and data.tipo != TipoProducto.KIT
            and producto.tipo == TipoProducto.KIT
            and await self._componente_repo.contar_por_kit(producto.id) > 0
        ):
            raise KitInvalido(
                "El kit tiene componentes; quitalos antes de cambiar el `tipo` a 'simple'."
            )
        if (
            data.tipo == TipoProducto.KIT
            and producto.tipo != TipoProducto.KIT
            and await self._unidad_repo.listar_por_producto(producto.id)
        ):
            raise KitInvalido(
                "El producto tiene presentaciones de venta; eliminalas antes de "
                "convertirlo en kit."
            )

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

        # Activar control por lote con stock existente crearía descuadre entre el
        # agregado `existencia` y el desglose `existencia_lote`.
        if (
            data.requiere_lote is True
            and not producto.requiere_lote
            and self._existencia_repo is not None
        ):
            existencias = await self._existencia_repo.listar(producto_id=producto.id)
            if any(e.cantidad > 0 for e in existencias):
                raise LoteInvalido(
                    "No se puede activar el control por lote con stock cargado. "
                    "Llevá el stock a 0 (salida/ajuste) y volvé a cargarlo por lote."
                )

        producto.actualizar(
            sku=data.sku,
            nombre=data.nombre,
            descripcion=data.descripcion,
            categoria_id=data.categoria_id,
            unidad_medida=data.unidad_medida,
            unidad_medida_id=data.unidad_medida_id,
            cambiar_unidad_medida_id=data.cambiar_unidad_medida_id,
            precio_venta=data.precio_venta,
            costo=data.costo,
            impuesto_tasa=data.impuesto_tasa,
            tipo=data.tipo,
            permite_stock_negativo=data.permite_stock_negativo,
            permite_venta_fraccionada=data.permite_venta_fraccionada,
            incremento_minimo_venta=data.incremento_minimo_venta,
            cambiar_incremento_minimo_venta=data.cambiar_incremento_minimo_venta,
            requiere_lote=data.requiere_lote,
            rastrea_instancia_abierta=data.rastrea_instancia_abierta,
            instancia_capacidad_default=data.instancia_capacidad_default,
            cambiar_instancia_capacidad_default=data.cambiar_instancia_capacidad_default,
            precio_incluye_impuesto=data.precio_incluye_impuesto,
            es_sobre_pedido=data.es_sobre_pedido,
            precio_mayoreo=data.precio_mayoreo,
            cantidad_minima_mayoreo=data.cantidad_minima_mayoreo,
            cambiar_mayoreo=data.cambiar_mayoreo,
            monedero_pct=data.monedero_pct,
            monedero_monto=data.monedero_monto,
            cambiar_monedero=data.cambiar_monedero,
            codigo_barras=data.codigo_barras,
            cambiar_codigo_barras=data.cambiar_codigo_barras,
            cambiar_descripcion=data.cambiar_descripcion,
        )
        if data.cambiar_mayoreo:
            _validar_mayoreo(producto.precio_mayoreo, producto.cantidad_minima_mayoreo)
        # Coherencia: si el producto queda rastreando instancias, necesita una
        # capacidad default > 0 para poder auto-abrir al vender a granel.
        if producto.rastrea_instancia_abierta and not (
            producto.instancia_capacidad_default
            and producto.instancia_capacidad_default > 0
        ):
            raise InstanciaConfigInvalida(
                "`rastrea_instancia_abierta` requiere `instancia_capacidad_default` > 0."
            )
        try:
            await self._repo.actualizar(producto)
        except IntegrityError as e:
            raise _traducir_integridad(e, producto.sku, producto.codigo_barras)
        return producto


class DesactivarProductoUseCase:
    def __init__(
        self,
        producto_repo: ProductoRepository,
        existencia_repo: ExistenciaRepository,
        componente_repo: ProductoComponenteRepository,
    ):
        self._repo = producto_repo
        self._existencia_repo = existencia_repo
        self._componente_repo = componente_repo

    async def ejecutar(self, producto_id: UUID, confirmar_con_stock: bool = False) -> Producto:
        producto = await self._repo.obtener_por_id(producto_id)
        if not producto:
            raise ProductoNoEncontrado(f"No existe el producto {producto_id}")

        if await self._componente_repo.es_componente_de_kit_activo(producto_id):
            raise ProductoEsComponenteDeKit(
                "Este producto es componente de un kit activo; quitalo de esas recetas "
                "antes de desactivarlo."
            )

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


class EliminarProductoUseCase:
    """Borrado FÍSICO del producto y de su catálogo propio (imágenes + objetos
    S3, presentaciones, receta como kit, lotes, existencia y existencia_lote).

    Solo si el producto NO tiene historial: sin movimientos de inventario y sin
    ventas que lo referencien. Si lo tiene -> `ProductoConHistorial` (409) y hay
    que usar `DesactivarProductoUseCase` (baja lógica).
    """

    def __init__(
        self,
        producto_repo: ProductoRepository,
        movimiento_repo: MovimientoRepository,
        componente_repo: ProductoComponenteRepository,
        almacen: AlmacenImagenes | None = None,
    ):
        self._repo = producto_repo
        self._mov_repo = movimiento_repo
        self._comp_repo = componente_repo
        self._almacen = almacen

    async def ejecutar(self, producto_id: UUID) -> None:
        producto = await self._repo.obtener_por_id(producto_id)
        if not producto:
            raise ProductoNoEncontrado(f"No existe el producto {producto_id}")

        if await self._mov_repo.existe_para_producto(producto_id):
            raise ProductoConHistorial(
                "El producto tiene movimientos de inventario registrados; no se "
                "puede borrar. Usá PATCH /productos/{id}/desactivar."
            )
        if await self._comp_repo.es_componente_de_kit_activo(producto_id):
            raise ProductoEsComponenteDeKit(
                "Este producto es componente de un kit activo; quitalo de esas "
                "recetas antes de borrarlo."
            )

        try:
            object_keys = await self._repo.eliminar_fisico(producto_id)
        except IntegrityError as e:
            # Lo referencia una venta (detalle_venta) u otro registro histórico.
            raise ProductoConHistorial(
                "El producto está referenciado por ventas u otros registros "
                "históricos; no se puede borrar. Usá PATCH /productos/{id}/desactivar."
            ) from e

        # Limpieza de S3 best-effort, ya con el DELETE en BD hecho (mismo
        # criterio que EliminarImagenUseCase).
        if self._almacen is not None:
            for key in object_keys:
                await self._almacen.eliminar(key)
                await self._almacen.eliminar(AlmacenImagenes.key_miniatura(key))
