from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.modules.pedidos.domain.value_objects import (
    TipoPedido, CanalPedido, EstadoPedido, EstadoEntrega,
)

__all__ = ["FiltroPedidos"]


@dataclass
class FiltroPedidos:
    sucursal_id: UUID | None = None
    cliente_id: UUID | None = None
    repartidor_id: UUID | None = None
    telefono: str | None = None
    tipo: TipoPedido | None = None
    canal: CanalPedido | None = None
    estado: EstadoPedido | None = None
    estado_entrega: EstadoEntrega | None = None
    desde: datetime | None = None
    hasta: datetime | None = None
