"""Casos de uso de la receta (BOM) de un producto kit.

Reglas:
- El `kit_id` debe existir y ser `tipo == kit`.
- Cada componente debe existir, estar activo, no ser el propio kit y no ser a su
  vez un kit (sin kits anidados en v1).
- `cantidad > 0`.
- No se repite un componente dentro del mismo kit.
"""
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from app.modules.inventario.domain.entities import Producto, ProductoComponente
from app.modules.inventario.domain.value_objects import TipoProducto
from app.modules.inventario.domain.exceptions import (
    ProductoNoEncontrado, KitInvalido, ComponenteInvalido, ComponenteDuplicado,
    ComponenteNoEncontrado,
)
from app.modules.inventario.application.ports.producto_repository import ProductoRepository
from app.modules.inventario.application.ports.componente_repository import (
    ProductoComponenteRepository,
)


async def _cargar_kit(repo: ProductoRepository, kit_id: UUID) -> Producto:
    kit = await repo.obtener_por_id(kit_id)
    if kit is None:
        raise ProductoNoEncontrado(f"No existe el producto {kit_id}")
    if kit.tipo != TipoProducto.KIT:
        raise KitInvalido(
            f"El producto {kit_id} no es un kit; cambiá su `tipo` a 'kit' primero."
        )
    return kit


async def _validar_componente(
    repo: ProductoRepository, kit_id: UUID, componente_id: UUID
) -> None:
    if componente_id == kit_id:
        raise ComponenteInvalido("Un kit no puede contenerse a sí mismo.")
    prod = await repo.obtener_por_id(componente_id)
    if prod is None:
        raise ComponenteInvalido(f"No existe el producto componente {componente_id}")
    if not prod.activo:
        raise ComponenteInvalido(f"El producto componente {componente_id} está inactivo.")
    if prod.tipo == TipoProducto.KIT:
        raise ComponenteInvalido(
            "Un kit no puede ser componente de otro kit (sin kits anidados)."
        )


# --------------------------------------------------------------------------- #
class ListarComponentesUseCase:
    def __init__(self, componente_repo: ProductoComponenteRepository, producto_repo: ProductoRepository):
        self._repo = componente_repo
        self._producto_repo = producto_repo

    async def ejecutar(
        self, kit_id: UUID, includes: frozenset[str] = frozenset()
    ) -> list[ProductoComponente]:
        prod = await self._producto_repo.obtener_por_id(kit_id)
        if prod is None:
            raise ProductoNoEncontrado(f"No existe el producto {kit_id}")
        return await self._repo.listar_por_kit(kit_id, includes)


# --------------------------------------------------------------------------- #
@dataclass
class AgregarComponenteInput:
    kit_id: UUID
    producto_componente_id: UUID
    cantidad: Decimal


class AgregarComponenteUseCase:
    def __init__(self, componente_repo: ProductoComponenteRepository, producto_repo: ProductoRepository):
        self._repo = componente_repo
        self._producto_repo = producto_repo

    async def ejecutar(self, data: AgregarComponenteInput) -> ProductoComponente:
        if data.cantidad is None or data.cantidad <= 0:
            raise ComponenteInvalido("La cantidad del componente debe ser mayor a 0.")
        await _cargar_kit(self._producto_repo, data.kit_id)
        await _validar_componente(self._producto_repo, data.kit_id, data.producto_componente_id)
        if await self._repo.obtener(data.kit_id, data.producto_componente_id) is not None:
            raise ComponenteDuplicado(
                f"El producto {data.producto_componente_id} ya es componente de este kit."
            )
        comp = ProductoComponente(
            producto_kit_id=data.kit_id,
            producto_componente_id=data.producto_componente_id,
            cantidad=data.cantidad,
        )
        await self._repo.agregar(comp)
        return comp


# --------------------------------------------------------------------------- #
@dataclass
class ActualizarComponenteInput:
    kit_id: UUID
    producto_componente_id: UUID
    cantidad: Decimal


class ActualizarComponenteUseCase:
    def __init__(self, componente_repo: ProductoComponenteRepository, producto_repo: ProductoRepository):
        self._repo = componente_repo
        self._producto_repo = producto_repo

    async def ejecutar(self, data: ActualizarComponenteInput) -> ProductoComponente:
        if data.cantidad is None or data.cantidad <= 0:
            raise ComponenteInvalido("La cantidad del componente debe ser mayor a 0.")
        await _cargar_kit(self._producto_repo, data.kit_id)
        actual = await self._repo.obtener(data.kit_id, data.producto_componente_id)
        if actual is None:
            raise ComponenteNoEncontrado(
                f"El producto {data.producto_componente_id} no es componente de este kit."
            )
        await self._repo.actualizar_cantidad(
            data.kit_id, data.producto_componente_id, data.cantidad
        )
        actual.cantidad = data.cantidad
        return actual


# --------------------------------------------------------------------------- #
class QuitarComponenteUseCase:
    def __init__(self, componente_repo: ProductoComponenteRepository, producto_repo: ProductoRepository):
        self._repo = componente_repo
        self._producto_repo = producto_repo

    async def ejecutar(self, kit_id: UUID, componente_id: UUID) -> None:
        await _cargar_kit(self._producto_repo, kit_id)
        if await self._repo.obtener(kit_id, componente_id) is None:
            raise ComponenteNoEncontrado(
                f"El producto {componente_id} no es componente de este kit."
            )
        await self._repo.quitar(kit_id, componente_id)


# --------------------------------------------------------------------------- #
@dataclass
class LineaRecetaInput:
    producto_componente_id: UUID
    cantidad: Decimal


@dataclass
class ReemplazarRecetaInput:
    kit_id: UUID
    componentes: list[LineaRecetaInput]


class ReemplazarRecetaUseCase:
    """PUT: valida la receta completa y la reemplaza en una sola transacción."""

    def __init__(self, componente_repo: ProductoComponenteRepository, producto_repo: ProductoRepository):
        self._repo = componente_repo
        self._producto_repo = producto_repo

    async def ejecutar(self, data: ReemplazarRecetaInput) -> list[ProductoComponente]:
        await _cargar_kit(self._producto_repo, data.kit_id)

        vistos: set[UUID] = set()
        nuevos: list[ProductoComponente] = []
        for linea in data.componentes:
            if linea.cantidad is None or linea.cantidad <= 0:
                raise ComponenteInvalido("La cantidad de cada componente debe ser mayor a 0.")
            if linea.producto_componente_id in vistos:
                raise ComponenteDuplicado(
                    f"El componente {linea.producto_componente_id} está repetido en la receta."
                )
            vistos.add(linea.producto_componente_id)
            await _validar_componente(
                self._producto_repo, data.kit_id, linea.producto_componente_id
            )
            nuevos.append(ProductoComponente(
                producto_kit_id=data.kit_id,
                producto_componente_id=linea.producto_componente_id,
                cantidad=linea.cantidad,
            ))

        await self._repo.reemplazar(data.kit_id, nuevos)
        return nuevos
