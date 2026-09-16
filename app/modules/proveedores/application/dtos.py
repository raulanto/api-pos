from dataclasses import dataclass
from uuid import UUID

from app.modules.proveedores.domain.value_objects import (
    EstadoPedidoProveedor, EstadoDevolucionProveedor,
)


@dataclass
class FiltroProveedores:
    activo: bool | None = None
    busqueda: str | None = None   # coincide contra codigo / razon_social / rfc


@dataclass
class FiltroPedidosProveedor:
    proveedor_id: UUID | None = None
    sucursal_id: UUID | None = None
    estado: EstadoPedidoProveedor | None = None


@dataclass
class FiltroRecepciones:
    proveedor_id: UUID | None = None
    sucursal_id: UUID | None = None
    pedido_id: UUID | None = None


@dataclass
class FiltroDevoluciones:
    proveedor_id: UUID | None = None
    estado: EstadoDevolucionProveedor | None = None
