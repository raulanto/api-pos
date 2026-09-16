from abc import ABC, abstractmethod
from uuid import UUID

from app.modules.proveedores.domain.entities import PedidoProveedor
from app.modules.proveedores.application.dtos import FiltroPedidosProveedor
from app.shared.responses import Page, PageParams, Sort


class PedidoProveedorRepository(ABC):
    @abstractmethod
    async def obtener_por_id(
        self, pedido_id: UUID, para_actualizar: bool = False,
    ) -> PedidoProveedor | None: ...

    @abstractmethod
    async def obtener_borrador_automatico(
        self, proveedor_id: UUID, sucursal_id: UUID,
    ) -> PedidoProveedor | None:
        """Un pedido `borrador` + `generado_automaticamente` abierto para ese
        proveedor+sucursal, si existe (el motor de reorden le suma líneas en
        vez de crear uno nuevo cada corrida)."""
        ...

    @abstractmethod
    async def guardar(self, pedido: PedidoProveedor) -> None: ...

    @abstractmethod
    async def actualizar(self, pedido: PedidoProveedor) -> None: ...

    @abstractmethod
    async def listar(
        self, filtro: FiltroPedidosProveedor, paginacion: PageParams, orden: Sort,
    ) -> Page: ...
