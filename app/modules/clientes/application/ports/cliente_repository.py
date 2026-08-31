from abc import ABC, abstractmethod
from uuid import UUID
from decimal import Decimal
from app.modules.clientes.domain.entities import Cliente

class ClienteRepository(ABC):
    @abstractmethod
    async def guardar(self, cliente: Cliente) -> None: ...

    @abstractmethod
    async def obtener_por_id(self, cliente_id: UUID) -> Cliente | None: ...

    @abstractmethod
    async def incrementar_saldo(self, cliente_id: UUID, monto: Decimal) -> None: ...
