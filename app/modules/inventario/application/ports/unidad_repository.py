from abc import ABC, abstractmethod
from uuid import UUID

from app.modules.inventario.domain.entities import ProductoUnidad


class ProductoUnidadRepository(ABC):
    @abstractmethod
    async def listar_por_producto(
        self, producto_id: UUID, incluir_inactivas: bool = False
    ) -> list[ProductoUnidad]: ...

    @abstractmethod
    async def obtener(self, unidad_id: UUID) -> ProductoUnidad | None: ...

    @abstractmethod
    async def obtener_por_codigo_barras(self, codigo_barras: str) -> ProductoUnidad | None: ...

    @abstractmethod
    async def existe_nombre(self, producto_id: UUID, nombre: str) -> bool: ...

    @abstractmethod
    async def crear(self, unidad: ProductoUnidad) -> None: ...

    @abstractmethod
    async def actualizar(self, unidad: ProductoUnidad) -> None: ...
