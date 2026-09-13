from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from app.modules.proveedores.domain.entities import PedidoProveedor, PedidoProveedorLinea
from app.modules.proveedores.domain.exceptions import PedidoProveedorNoEncontrado
from app.modules.proveedores.application.ports.pedido_proveedor_repository import (
    PedidoProveedorRepository,
)
from app.modules.proveedores.application.dtos import FiltroPedidosProveedor
from app.shared.responses import Page, PageParams, Sort


@dataclass
class LineaPedidoProveedorInput:
    producto_id: UUID
    cantidad_solicitada: Decimal
    precio_unitario: Decimal


@dataclass
class CrearPedidoProveedorInput:
    proveedor_id: UUID
    sucursal_id: UUID
    lineas: list[LineaPedidoProveedorInput]
    fecha_estimada_entrega: date | None = None
    notas: str | None = None


class CrearPedidoProveedorUseCase:
    def __init__(self, repo: PedidoProveedorRepository):
        self._repo = repo

    async def ejecutar(self, data: CrearPedidoProveedorInput) -> PedidoProveedor:
        lineas = [
            PedidoProveedorLinea.crear(l.producto_id, l.cantidad_solicitada, l.precio_unitario)
            for l in data.lineas
        ]
        pedido = PedidoProveedor.crear(
            proveedor_id=data.proveedor_id, sucursal_id=data.sucursal_id, lineas=lineas,
            fecha_estimada_entrega=data.fecha_estimada_entrega, notas=data.notas,
        )
        await self._repo.guardar(pedido)
        return pedido


async def _cargar(repo: PedidoProveedorRepository, pedido_id: UUID, para_actualizar: bool = False) -> PedidoProveedor:
    pedido = await repo.obtener_por_id(pedido_id, para_actualizar=para_actualizar)
    if pedido is None:
        raise PedidoProveedorNoEncontrado(f"No existe el pedido a proveedor {pedido_id}")
    return pedido


class ConfirmarEnvioPedidoProveedorUseCase:
    def __init__(self, repo: PedidoProveedorRepository):
        self._repo = repo

    async def ejecutar(self, pedido_id: UUID, usuario_id: UUID) -> PedidoProveedor:
        pedido = await _cargar(self._repo, pedido_id, para_actualizar=True)
        pedido.confirmar_envio(usuario_id)
        await self._repo.actualizar(pedido)
        return pedido


class CancelarPedidoProveedorUseCase:
    def __init__(self, repo: PedidoProveedorRepository):
        self._repo = repo

    async def ejecutar(self, pedido_id: UUID) -> PedidoProveedor:
        pedido = await _cargar(self._repo, pedido_id, para_actualizar=True)
        pedido.cancelar()
        await self._repo.actualizar(pedido)
        return pedido


class ObtenerPedidoProveedorUseCase:
    def __init__(self, repo: PedidoProveedorRepository):
        self._repo = repo

    async def ejecutar(self, pedido_id: UUID) -> PedidoProveedor:
        return await _cargar(self._repo, pedido_id)


class ListarPedidosProveedorUseCase:
    def __init__(self, repo: PedidoProveedorRepository):
        self._repo = repo

    async def ejecutar(
        self, filtro: FiltroPedidosProveedor, paginacion: PageParams, orden: Sort,
    ) -> Page:
        return await self._repo.listar(filtro, paginacion, orden)
