from abc import ABC, abstractmethod
from uuid import UUID

from app.modules.ventas.domain.entities import Devolucion


class DevolucionRepository(ABC):
    @abstractmethod
    async def crear(self, devolucion: Devolucion) -> None: ...

    @abstractmethod
    async def obtener_por_idempotency_key(self, key: str) -> Devolucion | None: ...

    @abstractmethod
    async def listar_por_venta(self, venta_id: UUID) -> list[Devolucion]: ...
