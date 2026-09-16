from dataclasses import dataclass
from typing import List
from uuid import UUID

from app.modules.ventas.application.use_cases.crear_venta import CrearVentaUseCase
from app.modules.usuarios.application.ports.usuario_repository import UsuarioRepository
from app.modules.pedidos.application.ports.pedido_repository import PedidoRepository
from app.modules.pedidos.application.use_cases.crear_pedido import (
    LineaPedidoInput, cotizar_a_detalles, validar_responsables,
)
from app.modules.pedidos.domain.entities import Pedido
from app.modules.pedidos.domain.exceptions import (
    PedidoNoEncontrado, PedidoNoEditable, MotivoDescuentoRequerido,
    DireccionEnvioRequerida,
)
from app.modules.pedidos.domain.value_objects import TipoPedido

_SIN_CAMBIO = object()


@dataclass
class ActualizarPedidoInput:
    pedido_id: UUID
    # Cualquiera de estos puede venir; `_SIN_CAMBIO` = no tocar.
    lineas: List[LineaPedidoInput] | None = None
    tipo: object = _SIN_CAMBIO
    canal: object = _SIN_CAMBIO
    cliente_id: object = _SIN_CAMBIO
    telefono: object = _SIN_CAMBIO
    descuento_total: object = _SIN_CAMBIO
    motivo_descuento: object = _SIN_CAMBIO
    codigo_cupon: object = _SIN_CAMBIO
    cliente_segmento: object = _SIN_CAMBIO
    notas: object = _SIN_CAMBIO
    fecha_promesa: object = _SIN_CAMBIO
    direccion_texto: object = _SIN_CAMBIO
    referencia_direccion: object = _SIN_CAMBIO


class ActualizarPedidoUseCase:
    def __init__(
        self, pedido_repo: PedidoRepository, crear_venta_uc: CrearVentaUseCase,
        usuario_repo: UsuarioRepository,
    ):
        self._repo = pedido_repo
        self._venta_uc = crear_venta_uc
        self._usuario_repo = usuario_repo

    async def ejecutar(self, data: ActualizarPedidoInput) -> Pedido:
        pedido = await self._repo.obtener_por_id(data.pedido_id)
        if pedido is None:
            raise PedidoNoEncontrado(f"No existe el pedido {data.pedido_id}")
        if not pedido.editable:
            raise PedidoNoEditable(
                f"El pedido {pedido.id} está '{pedido.estado.value}'; sólo se edita en borrador."
            )

        def _set(attr: str, val: object) -> None:
            if val is not _SIN_CAMBIO:
                setattr(pedido, attr, val)

        # `tipo` primero: reajusta la entrega y limpia los datos de envío si pasa
        # a `mostrador` (así el resto de `_set`, ej. una `direccion_texto` nueva,
        # queda coherente).
        if data.tipo is not _SIN_CAMBIO:
            pedido.cambiar_tipo(data.tipo)
        _set("canal", data.canal)
        _set("cliente_id", data.cliente_id)
        _set("telefono", data.telefono)
        _set("descuento_total", data.descuento_total)
        _set("motivo_descuento", data.motivo_descuento)
        _set("codigo_cupon", data.codigo_cupon)
        _set("cliente_segmento", data.cliente_segmento)
        _set("notas", data.notas)
        _set("fecha_promesa", data.fecha_promesa)
        _set("direccion_texto", data.direccion_texto)
        _set("referencia_direccion", data.referencia_direccion)

        # Re-cotiza si cambian líneas o algo que afecte precio (cupón/segmento/desc).
        reprice = data.lineas is not None or any(
            v is not _SIN_CAMBIO
            for v in (data.descuento_total, data.codigo_cupon, data.cliente_segmento)
        )
        if reprice:
            fuente = _FuentePrecio(pedido, data.lineas)
            nuevas = await cotizar_a_detalles(self._venta_uc, fuente)
            await validar_responsables(self._usuario_repo, nuevas)
            pedido.reemplazar_lineas(nuevas)

        _validar(pedido)
        await self._repo.actualizar(pedido)
        return pedido


class _FuentePrecio:
    """Adapta un Pedido (+ líneas nuevas opcionales) a lo que espera
    `cotizar_a_detalles`: atributos `sucursal_id`, `lineas`, `descuento_total`,
    `cliente_segmento`, `codigo_cupon`, `telefono`. Conserva `asignado_a` de las
    líneas actuales cuando no se mandan líneas nuevas."""
    def __init__(self, pedido: Pedido, lineas_nuevas: List[LineaPedidoInput] | None):
        self.sucursal_id = pedido.sucursal_id
        self.descuento_total = pedido.descuento_total
        self.cliente_segmento = pedido.cliente_segmento
        self.codigo_cupon = pedido.codigo_cupon
        self.telefono = pedido.telefono
        if lineas_nuevas is not None:
            self.lineas = lineas_nuevas
        else:
            self.lineas = [
                LineaPedidoInput(
                    producto_id=l.producto_id, cantidad=l.cantidad,
                    precio_unitario=l.precio_unitario, descuento_linea=l.descuento_linea,
                    impuesto_tasa=l.impuesto_tasa, producto_unidad_id=l.producto_unidad_id,
                    asignado_a=l.asignado_a,
                ) for l in pedido.lineas
            ]


def _validar(pedido: Pedido) -> None:
    hay_manual = pedido.descuento_total and pedido.descuento_total > 0
    hay_manual = hay_manual or any(l.descuento_linea > 0 for l in pedido.lineas)
    if hay_manual and not (pedido.motivo_descuento and pedido.motivo_descuento.strip()):
        raise MotivoDescuentoRequerido(
            "El descuento manual del pedido requiere `motivo_descuento`."
        )
    if pedido.tipo == TipoPedido.DOMICILIO and not (
        pedido.direccion_texto and pedido.direccion_texto.strip()
    ):
        raise DireccionEnvioRequerida("Un pedido a domicilio necesita `direccion_texto`.")
