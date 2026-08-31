from abc import ABC, abstractmethod
from decimal import Decimal
from uuid import UUID

from app.modules.clientes.domain.entities import Cliente
from app.modules.clientes.application.dtos import FiltroClientes
from app.shared.responses import Page, PageParams, Sort


class ClienteRepository(ABC):
    """Operaciones de persistencia de clientes.

    Las escrituras hacen `add`/`flush`; el commit lo cierra `get_db()`.
    """

    @abstractmethod
    async def guardar(self, cliente: Cliente) -> None: ...

    @abstractmethod
    async def actualizar(self, cliente: Cliente) -> None: ...

    @abstractmethod
    async def obtener_por_id(self, cliente_id: UUID) -> Cliente | None: ...

    @abstractmethod
    async def buscar_por_email(self, email: str, solo_activos: bool = True) -> Cliente | None: ...

    @abstractmethod
    async def listar(
        self, filtro: FiltroClientes, paginacion: PageParams, orden: Sort
    ) -> Page: ...

    @abstractmethod
    async def incrementar_saldo(self, cliente_id: UUID, monto: Decimal) -> None: ...

    @abstractmethod
    async def decrementar_saldo(self, cliente_id: UUID, monto: Decimal) -> None: ...

    @abstractmethod
    async def actualizar_limite_credito(self, cliente_id: UUID, nuevo_limite: Decimal) -> None: ...

    @abstractmethod
    async def desactivar(self, cliente_id: UUID) -> None: ...
