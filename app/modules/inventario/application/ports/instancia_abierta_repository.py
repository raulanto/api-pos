from abc import ABC, abstractmethod
from decimal import Decimal
from uuid import UUID

from app.modules.inventario.domain.entities import InstanciaAbierta
from app.modules.inventario.application.dtos import FiltroInstancias
from app.shared.responses import Page, PageParams, Sort


class InstanciaAbiertaRepository(ABC):
    @abstractmethod
    async def crear(self, instancia: InstanciaAbierta) -> None: ...

    @abstractmethod
    async def obtener(self, instancia_id: UUID) -> InstanciaAbierta | None: ...

    @abstractmethod
    async def actualizar(self, instancia: InstanciaAbierta) -> None: ...

    @abstractmethod
    async def listar(
        self, filtro: FiltroInstancias, paginacion: PageParams, orden: Sort,
    ) -> Page: ...

    @abstractmethod
    async def listar_abiertas(
        self, producto_id: UUID, sucursal_id: UUID,
    ) -> list[InstanciaAbierta]:
        """Instancias en estado `abierta` de ese producto/sucursal, ordenadas
        FIFO por `abierta_at` (la más vieja primero) para el plan de consumo."""
        ...

    @abstractmethod
    async def saldo_abierto(
        self, producto_id: UUID, sucursal_id: UUID, lote_id: UUID | None = None,
    ) -> Decimal:
        """Suma del `saldo` de las instancias `abierta` de ese producto/sucursal
        (opcionalmente acotado a un lote). 0 si no hay ninguna."""
        ...
