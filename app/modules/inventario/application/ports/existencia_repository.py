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

    @abstractmethod
    async def listar(
        self,
        producto_id: UUID | None = None,
        sucursal_id: UUID | None = None,
    ) -> list[Existencia]: ...

    @abstractmethod
    async def listar_bajo_stock(self, sucursal_id: UUID | None = None) -> list[Existencia]: ...

    @abstractmethod
    async def actualizar_umbrales(
        self,
        producto_id: UUID,
        sucursal_id: UUID,
        stock_minimo: Decimal,
        stock_maximo: Decimal | None,
    ) -> None: ...
