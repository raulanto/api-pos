"""Casos de uso de las presentaciones de venta (producto_unidad).

Reglas:
- El producto debe existir y NO ser un kit (un kit no tiene stock base).
- `factor > 0`.
- `nombre` único por producto (entre presentaciones activas).
- `codigo_barras` (si se da) no puede chocar con el de otro producto ni con el
  de otra presentación activa.
- La baja es lógica: las ventas históricas siguen apuntando a la fila.
"""
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from app.modules.inventario.domain.entities import Producto, ProductoUnidad
from app.modules.inventario.domain.value_objects import TipoProducto
from app.modules.inventario.domain.exceptions import (
    ProductoNoEncontrado, UnidadNoEncontrada, UnidadInvalida, UnidadDuplicada,
    CodigoBarrasUnidadDuplicado,
)
from app.modules.inventario.application.ports.producto_repository import ProductoRepository
from app.modules.inventario.application.ports.unidad_repository import (
    ProductoUnidadRepository,
)


def _resolver_factor(
    factor: Decimal | None, unidades_por_base: Decimal | None
) -> Decimal:
    """Acepta el factor directo (unidades base por 1 presentación, p. ej. Reja
    x24 => 24) o su recíproco `unidades_por_base` (cuántas de esta presentación
    entran en 1 unidad base, p. ej. 6 latas por reja => 6)."""
    if (factor is None) == (unidades_por_base is None):
        raise UnidadInvalida(
            "Indicá exactamente uno de `factor` o `unidades_por_base`."
        )
    if factor is not None:
        if factor <= 0:
            raise UnidadInvalida("`factor` debe ser mayor a 0.")
        return factor
    if unidades_por_base <= 0:
        raise UnidadInvalida("`unidades_por_base` debe ser mayor a 0.")
    return (Decimal("1") / unidades_por_base).quantize(Decimal("0.000001"))


async def _cargar_producto(repo: ProductoRepository, producto_id: UUID) -> Producto:
    producto = await repo.obtener_por_id(producto_id)
    if producto is None:
        raise ProductoNoEncontrado(f"No existe el producto {producto_id}")
    if producto.tipo == TipoProducto.KIT:
        raise UnidadInvalida(
            "Un kit no lleva presentaciones de venta; su stock se resuelve por receta."
        )
    return producto


async def _validar_codigo_barras(
    producto_repo: ProductoRepository,
    unidad_repo: ProductoUnidadRepository,
    codigo_barras: str,
    unidad_id: UUID | None = None,
) -> None:
    if await producto_repo.buscar_por_codigo_barras(codigo_barras) is not None:
        raise CodigoBarrasUnidadDuplicado(
            f"El código de barras '{codigo_barras}' ya lo usa un producto."
        )
    otra = await unidad_repo.obtener_por_codigo_barras(codigo_barras)
    if otra is not None and otra.id != unidad_id:
        raise CodigoBarrasUnidadDuplicado(
            f"El código de barras '{codigo_barras}' ya lo usa otra presentación."
        )


# --------------------------------------------------------------------------- #
class ListarUnidadesUseCase:
    def __init__(self, unidad_repo: ProductoUnidadRepository, producto_repo: ProductoRepository):
        self._repo = unidad_repo
        self._producto_repo = producto_repo

    async def ejecutar(
        self, producto_id: UUID, incluir_inactivas: bool = False
    ) -> list[ProductoUnidad]:
        prod = await self._producto_repo.obtener_por_id(producto_id)
        if prod is None:
            raise ProductoNoEncontrado(f"No existe el producto {producto_id}")
        return await self._repo.listar_por_producto(producto_id, incluir_inactivas)


# --------------------------------------------------------------------------- #
@dataclass
class AgregarUnidadInput:
    producto_id: UUID
    nombre: str
    unidad_medida: str
    precio_venta: Decimal
    factor: Decimal | None = None
    unidades_por_base: Decimal | None = None
    codigo_barras: str | None = None


class AgregarUnidadUseCase:
    def __init__(self, unidad_repo: ProductoUnidadRepository, producto_repo: ProductoRepository):
        self._repo = unidad_repo
        self._producto_repo = producto_repo

    async def ejecutar(self, data: AgregarUnidadInput) -> ProductoUnidad:
        factor = _resolver_factor(data.factor, data.unidades_por_base)
        await _cargar_producto(self._producto_repo, data.producto_id)

        nombre = data.nombre.strip()
        if await self._repo.existe_nombre(data.producto_id, nombre):
            raise UnidadDuplicada(f"Ya existe una presentación '{nombre}' para este producto.")

        codigo = data.codigo_barras.strip() if data.codigo_barras else None
        if codigo:
            await _validar_codigo_barras(self._producto_repo, self._repo, codigo)

        unidad = ProductoUnidad.crear(
            producto_id=data.producto_id,
            nombre=nombre,
            unidad_medida=data.unidad_medida.strip(),
            factor=factor,
            precio_venta=data.precio_venta,
            codigo_barras=codigo,
        )
        await self._repo.crear(unidad)
        return unidad


# --------------------------------------------------------------------------- #
@dataclass
class ActualizarUnidadInput:
    producto_id: UUID
    unidad_id: UUID
    nombre: str | None = None
    unidad_medida: str | None = None
    factor: Decimal | None = None
    unidades_por_base: Decimal | None = None
    precio_venta: Decimal | None = None
    codigo_barras: str | None = None
    cambiar_codigo_barras: bool = False


class ActualizarUnidadUseCase:
    def __init__(self, unidad_repo: ProductoUnidadRepository, producto_repo: ProductoRepository):
        self._repo = unidad_repo
        self._producto_repo = producto_repo

    async def ejecutar(self, data: ActualizarUnidadInput) -> ProductoUnidad:
        unidad = await self._repo.obtener(data.unidad_id)
        if unidad is None or unidad.producto_id != data.producto_id:
            raise UnidadNoEncontrada(
                f"El producto {data.producto_id} no tiene la presentación {data.unidad_id}."
            )

        nuevo_factor: Decimal | None = None
        if data.factor is not None or data.unidades_por_base is not None:
            nuevo_factor = _resolver_factor(data.factor, data.unidades_por_base)

        if data.nombre is not None:
            nombre = data.nombre.strip()
            if nombre.lower() != unidad.nombre.lower() and await self._repo.existe_nombre(
                data.producto_id, nombre
            ):
                raise UnidadDuplicada(
                    f"Ya existe una presentación '{nombre}' para este producto."
                )

        if data.cambiar_codigo_barras and data.codigo_barras:
            await _validar_codigo_barras(
                self._producto_repo, self._repo, data.codigo_barras.strip(), unidad.id
            )

        unidad.actualizar(
            nombre=data.nombre.strip() if data.nombre is not None else None,
            unidad_medida=data.unidad_medida.strip() if data.unidad_medida is not None else None,
            factor=nuevo_factor,
            precio_venta=data.precio_venta,
            codigo_barras=data.codigo_barras.strip() if data.codigo_barras else None,
            cambiar_codigo_barras=data.cambiar_codigo_barras,
        )
        await self._repo.actualizar(unidad)
        return unidad


# --------------------------------------------------------------------------- #
class DesactivarUnidadUseCase:
    def __init__(self, unidad_repo: ProductoUnidadRepository, producto_repo: ProductoRepository):
        self._repo = unidad_repo
        self._producto_repo = producto_repo

    async def ejecutar(self, producto_id: UUID, unidad_id: UUID) -> None:
        unidad = await self._repo.obtener(unidad_id)
        if unidad is None or unidad.producto_id != producto_id:
            raise UnidadNoEncontrada(
                f"El producto {producto_id} no tiene la presentación {unidad_id}."
            )
        unidad.desactivar()
        await self._repo.actualizar(unidad)


# --------------------------------------------------------------------------- #
@dataclass
class ResolucionCodigo:
    producto_id: UUID
    unidad_id: UUID | None
    nombre_unidad: str
    unidad_medida: str
    factor: Decimal
    precio_venta: Decimal


class ResolverCodigoBarrasUseCase:
    """Escaneo en el POS: resuelve un código contra el producto (unidad base) o
    contra una presentación, y devuelve el `factor` y `precio` a usar en la línea."""

    def __init__(self, unidad_repo: ProductoUnidadRepository, producto_repo: ProductoRepository):
        self._repo = unidad_repo
        self._producto_repo = producto_repo

    async def ejecutar(self, codigo_barras: str) -> ResolucionCodigo:
        producto = await self._producto_repo.buscar_por_codigo_barras(codigo_barras)
        if producto is not None:
            return ResolucionCodigo(
                producto_id=producto.id,
                unidad_id=None,
                nombre_unidad="Unidad",
                unidad_medida=producto.unidad_medida,
                factor=Decimal("1"),
                precio_venta=producto.precio_venta,
            )
        unidad = await self._repo.obtener_por_codigo_barras(codigo_barras)
        if unidad is not None:
            return ResolucionCodigo(
                producto_id=unidad.producto_id,
                unidad_id=unidad.id,
                nombre_unidad=unidad.nombre,
                unidad_medida=unidad.unidad_medida,
                factor=unidad.factor,
                precio_venta=unidad.precio_venta,
            )
        raise ProductoNoEncontrado(
            f"Ningún producto ni presentación tiene el código de barras '{codigo_barras}'."
        )
