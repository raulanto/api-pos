from abc import ABC, abstractmethod
from uuid import UUID
from app.modules.ventas.domain.entities import Venta
from app.modules.ventas.domain.value_objects import EstadoVenta
from app.modules.ventas.application.dtos import FiltroVentas, Paginacion, Pagina

class VentaRepository(ABC):
    @abstractmethod
    async def guardar(self, venta: Venta) -> None: ...

    @abstractmethod
    async def obtener_por_id(self, venta_id: UUID) -> Venta | None: ...

    @abstractmethod
    async def obtener_por_idempotency_key(self, key: str) -> Venta | None: ...

    @abstractmethod
    async def actualizar_estado(self, venta_id: UUID, estado: EstadoVenta) -> None: ...

    @abstractmethod
    async def listar(self, filtro: FiltroVentas, paginacion: Paginacion) -> Pagina: ...
