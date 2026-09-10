from uuid import UUID

from app.modules.pedidos.application.dtos import FiltroPedidos
from app.modules.pedidos.application.ports.pedido_repository import PedidoRepository
from app.modules.pedidos.domain.entities import Pedido
from app.modules.pedidos.domain.exceptions import PedidoNoEncontrado
from app.shared.responses import Page, PageParams, Sort


class ListarPedidosUseCase:
    def __init__(self, repo: PedidoRepository):
        self._repo = repo

    async def ejecutar(
        self, filtro: FiltroPedidos, paginacion: PageParams, orden: Sort,
        includes: frozenset[str] = frozenset(),
    ) -> Page:
        return await self._repo.listar(filtro, paginacion, orden, includes)


class ObtenerPedidoUseCase:
    def __init__(self, repo: PedidoRepository):
        self._repo = repo

    async def ejecutar(
        self, pedido_id: UUID, includes: frozenset[str] = frozenset()
    ) -> Pedido:
        pedido = await self._repo.obtener_por_id(pedido_id, includes)
        if pedido is None:
            raise PedidoNoEncontrado(f"No existe el pedido {pedido_id}")
        return pedido


class ResumenPedidosUseCase:
    """Conteos para un tablero de operación (pendientes por estado / entrega)."""
    def __init__(self, repo: PedidoRepository):
        self._repo = repo

    async def ejecutar(self, sucursal_id: UUID | None) -> dict:
        return {
            "por_estado": await self._repo.contar_por_estado(sucursal_id),
            "por_estado_entrega": await self._repo.contar_por_estado_entrega(sucursal_id),
        }
