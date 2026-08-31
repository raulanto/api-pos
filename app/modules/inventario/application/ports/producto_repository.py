from abc import ABC, abstractmethod
from uuid import UUID
from app.modules.inventario.domain.entities import Producto

class ProductoRepository(ABC):
    @abstractmethod
    async def guardar(self, producto: Producto) -> None: ...

    @abstractmethod
    async def obtener_por_id(self, producto_id: UUID) -> Producto | None: ...
