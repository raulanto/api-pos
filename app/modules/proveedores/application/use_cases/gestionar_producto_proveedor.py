from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from sqlalchemy.exc import IntegrityError

from app.modules.proveedores.domain.entities import ProductoProveedor
from app.modules.proveedores.domain.exceptions import (
    ProductoProveedorNoEncontrado, ProductoProveedorYaExiste, YaHayProveedorPrincipal,
)
from app.modules.proveedores.application.ports.producto_proveedor_repository import (
    ProductoProveedorRepository,
)


@dataclass
class VincularProductoProveedorInput:
    producto_id: UUID
    proveedor_id: UUID
    precio_compra: Decimal
    tiempo_entrega_dias: int
    stock_minimo: Decimal
    cantidad_reorden: Decimal
    codigo_proveedor: str | None = None
    stock_maximo: Decimal | None = None
    es_proveedor_principal: bool = False


class VincularProductoProveedorUseCase:
    def __init__(self, repo: ProductoProveedorRepository):
        self._repo = repo

    async def ejecutar(self, data: VincularProductoProveedorInput) -> ProductoProveedor:
        existente = await self._repo.obtener_por_par(data.producto_id, data.proveedor_id)
        if existente is not None and existente.activo:
            raise ProductoProveedorYaExiste(
                "Ya existe un vínculo activo entre este producto y este proveedor."
            )
        pp = ProductoProveedor.crear(
            producto_id=data.producto_id, proveedor_id=data.proveedor_id,
            precio_compra=data.precio_compra, tiempo_entrega_dias=data.tiempo_entrega_dias,
            stock_minimo=data.stock_minimo, cantidad_reorden=data.cantidad_reorden,
            codigo_proveedor=data.codigo_proveedor, stock_maximo=data.stock_maximo,
            es_proveedor_principal=data.es_proveedor_principal,
        )
        if data.es_proveedor_principal:
            actual = await self._repo.obtener_principal(data.producto_id)
            if actual is not None:
                raise YaHayProveedorPrincipal(
                    f"El proveedor {actual.proveedor_id} ya es el principal de este producto."
                )
        try:
            await self._repo.guardar(pp)
        except IntegrityError as e:
            detalle = str(getattr(e, "orig", e)).lower()
            if "principal" in detalle:
                raise YaHayProveedorPrincipal(
                    "Otro proveedor ya es el principal (activo) de este producto."
                )
            raise ProductoProveedorYaExiste(
                "Ya existe un vínculo entre este producto y este proveedor."
            )
        return pp


class DesvincularProductoProveedorUseCase:
    def __init__(self, repo: ProductoProveedorRepository):
        self._repo = repo

    async def ejecutar(self, id_: UUID) -> ProductoProveedor:
        pp = await self._repo.obtener_por_id(id_)
        if pp is None:
            raise ProductoProveedorNoEncontrado(f"No existe el vínculo {id_}")
        pp.desactivar()
        await self._repo.actualizar(pp)
        return pp


class MarcarProveedorPrincipalUseCase:
    """Marca `pp` como principal y desmarca (a nivel dominio) al que lo era
    antes — el índice único parcial de BD es la red de seguridad."""

    def __init__(self, repo: ProductoProveedorRepository):
        self._repo = repo

    async def ejecutar(self, id_: UUID) -> ProductoProveedor:
        pp = await self._repo.obtener_por_id(id_)
        if pp is None:
            raise ProductoProveedorNoEncontrado(f"No existe el vínculo {id_}")
        if pp.es_proveedor_principal:
            return pp
        actual = await self._repo.obtener_principal(pp.producto_id)
        if actual is not None and actual.id != pp.id:
            actual.quitar_principal()
            await self._repo.actualizar(actual)
        pp.marcar_principal()
        try:
            await self._repo.actualizar(pp)
        except IntegrityError:
            raise YaHayProveedorPrincipal(
                "Otro proveedor ya es el principal (activo) de este producto."
            )
        return pp


class ListarProductoProveedorPorProductoUseCase:
    def __init__(self, repo: ProductoProveedorRepository):
        self._repo = repo

    async def ejecutar(self, producto_id: UUID, incluir_inactivos: bool = False) -> list[ProductoProveedor]:
        return await self._repo.listar_por_producto(producto_id, incluir_inactivos)


class ListarProductoProveedorPorProveedorUseCase:
    def __init__(self, repo: ProductoProveedorRepository):
        self._repo = repo

    async def ejecutar(self, proveedor_id: UUID, incluir_inactivos: bool = False) -> list[ProductoProveedor]:
        return await self._repo.listar_por_proveedor(proveedor_id, incluir_inactivos)
