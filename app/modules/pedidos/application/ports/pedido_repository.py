from abc import ABC, abstractmethod
from uuid import UUID

from app.modules.pedidos.application.dtos import FiltroPedidos
from app.modules.pedidos.domain.entities import Pedido, PedidoPago
from app.shared.responses import Page, PageParams, Sort


class PedidoRepository(ABC):
    @abstractmethod
    async def guardar(self, pedido: Pedido) -> None:
        ...

    @abstractmethod
    async def actualizar(self, pedido: Pedido) -> None:
        """Persiste cabecera + líneas (reemplaza líneas) + estado de entrega."""
        ...

    @abstractmethod
    async def agregar_pago(self, pago: PedidoPago) -> None:
        ...

    @abstractmethod
    async def marcar_pagos_reembolsados(self, pedido_id: UUID) -> None:
        ...

    @abstractmethod
    async def obtener_por_id(
        self, pedido_id: UUID, includes: frozenset[str] = frozenset()
    ) -> Pedido | None:
        ...

    @abstractmethod
    async def obtener_por_idempotency_key(self, key: str) -> Pedido | None:
        ...

    @abstractmethod
    async def listar(
        self, filtro: FiltroPedidos, paginacion: PageParams, orden: Sort,
        includes: frozenset[str] = frozenset(),
    ) -> Page:
        ...

    @abstractmethod
    async def contar_por_estado(self, sucursal_id: UUID | None) -> dict[str, int]:
        ...

    @abstractmethod
    async def contar_por_estado_entrega(self, sucursal_id: UUID | None) -> dict[str, int]:
        ...
