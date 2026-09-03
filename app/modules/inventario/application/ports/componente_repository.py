from abc import ABC, abstractmethod
from decimal import Decimal
from uuid import UUID

from app.modules.inventario.domain.entities import ProductoComponente


class ProductoComponenteRepository(ABC):
    @abstractmethod
    async def listar_por_kit(
        self, kit_id: UUID, includes: frozenset[str] = frozenset()
    ) -> list[ProductoComponente]: ...

    @abstractmethod
    async def obtener(
        self, kit_id: UUID, componente_id: UUID
    ) -> ProductoComponente | None: ...

    @abstractmethod
    async def agregar(self, componente: ProductoComponente) -> None: ...

    @abstractmethod
    async def actualizar_cantidad(
        self, kit_id: UUID, componente_id: UUID, cantidad: Decimal
    ) -> None: ...

    @abstractmethod
    async def quitar(self, kit_id: UUID, componente_id: UUID) -> None: ...

    @abstractmethod
    async def reemplazar(
        self, kit_id: UUID, componentes: list[ProductoComponente]
    ) -> None: ...

    @abstractmethod
    async def contar_por_kit(self, kit_id: UUID) -> int: ...

    @abstractmethod
    async def es_componente_de_kit_activo(self, producto_id: UUID) -> bool: ...
