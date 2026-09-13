from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from app.modules.proveedores.domain.entities import PedidoProveedor, PedidoProveedorLinea
from app.modules.proveedores.application.ports.producto_proveedor_repository import (
    ProductoProveedorRepository,
)
from app.modules.proveedores.application.ports.pedido_proveedor_repository import (
    PedidoProveedorRepository,
)
from app.modules.inventario.application.ports.existencia_repository import ExistenciaRepository


@dataclass
class ReordenGenerado:
    pedido: PedidoProveedor
    fue_creado: bool   # False = se le agregaron líneas a un borrador ya abierto


class EvaluarReordenUseCase:
    """Compara el stock actual de cada producto (contra su proveedor
    principal) en una sucursal contra `producto_proveedor.stock_minimo`. Sólo
    genera pedidos `borrador`; confirmar el envío es una acción manual aparte
    (`ConfirmarEnvioPedidoProveedorUseCase`)."""

    def __init__(
        self,
        producto_proveedor_repo: ProductoProveedorRepository,
        pedido_repo: PedidoProveedorRepository,
        existencia_repo: ExistenciaRepository,
    ):
        self._pp_repo = producto_proveedor_repo
        self._pedido_repo = pedido_repo
        self._existencia_repo = existencia_repo

    async def ejecutar(self, sucursal_id: UUID, usuario_id: UUID) -> list[ReordenGenerado]:
        principales = await self._pp_repo.listar_principales_activos()
        por_proveedor: dict[UUID, list[PedidoProveedorLinea]] = {}

        for pp in principales:
            existencia = await self._existencia_repo.obtener(pp.producto_id, sucursal_id)
            stock_actual = existencia.cantidad if existencia is not None else Decimal("0")
            if stock_actual >= pp.stock_minimo:
                continue
            linea = PedidoProveedorLinea.crear(
                producto_id=pp.producto_id, cantidad_solicitada=pp.cantidad_reorden,
                precio_unitario=pp.precio_compra,
            )
            por_proveedor.setdefault(pp.proveedor_id, []).append(linea)

        resultados: list[ReordenGenerado] = []
        for proveedor_id, lineas in por_proveedor.items():
            borrador = await self._pedido_repo.obtener_borrador_automatico(proveedor_id, sucursal_id)
            if borrador is not None:
                borrador.agregar_lineas(lineas)
                await self._pedido_repo.actualizar(borrador)
                resultados.append(ReordenGenerado(pedido=borrador, fue_creado=False))
            else:
                nuevo = PedidoProveedor.crear(
                    proveedor_id=proveedor_id, sucursal_id=sucursal_id, lineas=lineas,
                    generado_automaticamente=True, generado_por=usuario_id,
                )
                await self._pedido_repo.guardar(nuevo)
                resultados.append(ReordenGenerado(pedido=nuevo, fue_creado=True))
        return resultados
