from abc import ABC, abstractmethod
from uuid import UUID
from decimal import Decimal
from app.modules.inventario.domain.entities import Existencia

class ExistenciaRepository(ABC):
    @abstractmethod
    async def obtener(self, producto_id: UUID, sucursal_id: UUID) -> Existencia | None: ...

    @abstractmethod
    async def actualizar_cantidad(self, producto_id: UUID, sucursal_id: UUID, nueva_cantidad: Decimal) -> None: ...

    @abstractmethod
    async def crear(self, existencia: Existencia) -> None: ...
