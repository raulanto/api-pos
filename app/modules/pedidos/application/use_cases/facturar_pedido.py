from dataclasses import dataclass, field
from decimal import Decimal
from typing import List
from uuid import UUID

from app.modules.ventas.application.use_cases.crear_venta import (
    CrearVentaUseCase, CrearVentaInput, LineaInput, PagoInput,
)
from app.modules.ventas.application.ports.venta_repository import VentaRepository
from app.modules.ventas.application.ports.event_port import EventPort
from app.modules.ventas.domain.entities import Venta, DetalleVenta
from app.modules.pedidos.application.ports.pedido_repository import PedidoRepository
from app.modules.pedidos.domain.entities import Pedido
from app.modules.pedidos.domain.value_objects import EstadoPedido, EstadoEntrega, TipoPedido
from app.modules.pedidos.domain.exceptions import (
    PedidoNoEncontrado, PedidoYaFacturado, TransicionPedidoInvalida,
    ProductoEnvioNoConfigurado, EntregaNoAplica,
)


@dataclass
class FacturarPedidoInput:
    pedido_id: UUID
    usuario_id: UUID
    caja_turno_id: UUID
    pagos: List[PagoInput] = field(default_factory=list)   # pagos al momento de facturar
    recalcular_precios: bool = False   # True = re-corre mayoreo/promos vigentes
    puede_descuento_manual: bool = False   # sólo se mira si recalcular_precios
    rol_id: UUID | None = None
    idempotency_key: str | None = None


class FacturarPedidoUseCase:
    """Convierte un pedido `confirmado` en una `Venta` real reusando
    `CrearVentaUseCase` (stock, caja, monedero, cupón, crédito). El pedido queda
    `facturado` con `venta_id`. El `costo_envio` entra como una línea del
    producto-servicio configurado."""

    def __init__(
        self, pedido_repo: PedidoRepository, venta_repo: VentaRepository,
        crear_venta_uc: CrearVentaUseCase, event_port: EventPort,
        producto_envio_id: UUID | None,
    ):
        self._repo = pedido_repo
        self._venta_repo = venta_repo
        self._venta_uc = crear_venta_uc
        self._event_port = event_port
        self._producto_envio_id = producto_envio_id

    async def ejecutar(self, data: FacturarPedidoInput) -> Venta:
        pedido = await self._repo.obtener_por_id(data.pedido_id)
        if pedido is None:
            raise PedidoNoEncontrado(f"No existe el pedido {data.pedido_id}")

        if pedido.estado == EstadoPedido.FACTURADO:
            # Idempotente: devolver la venta ya emitida.
            venta = await self._venta_repo.obtener_por_id(pedido.venta_id)
            if venta is not None:
                return venta
            raise PedidoYaFacturado(f"El pedido {pedido.id} ya está facturado.")
        if pedido.estado != EstadoPedido.CONFIRMADO:
            raise TransicionPedidoInvalida(
                f"Sólo se factura un pedido confirmado (está '{pedido.estado.value}')."
            )
        if pedido.tipo == TipoPedido.DOMICILIO and pedido.estado_entrega == EstadoEntrega.FALLIDO:
            raise EntregaNoAplica(
                "La entrega falló; reintentá o cancelá el pedido antes de facturar."
            )

        con_envio = bool(pedido.costo_envio and pedido.costo_envio > 0)
        if con_envio and self._producto_envio_id is None:
            raise ProductoEnvioNoConfigurado(
                "El pedido tiene `costo_envio` pero falta configurar "
                "`pedidos_producto_envio_id`."
            )

        anticipos = [
            PagoInput(monto=p.monto, metodo_pago=p.metodo_pago)
            for p in pedido.pagos if not p.reembolsado
        ]
        pagos = anticipos + list(data.pagos)

        entrada = CrearVentaInput(
            sucursal_id=pedido.sucursal_id,
            caja_turno_id=data.caja_turno_id,
            usuario_id=data.usuario_id,
            cliente_id=pedido.cliente_id,
            descuento_total=pedido.descuento_total,
            lineas=[],
            pagos=pagos,
            idempotency_key=data.idempotency_key,
            telefono=pedido.telefono,
            motivo_descuento=pedido.motivo_descuento,
            codigo_cupon=pedido.codigo_cupon,
        )

        if data.recalcular_precios:
            entrada.lineas = [
                LineaInput(
                    producto_id=l.producto_id, cantidad=l.cantidad,
                    precio_unitario=l.precio_unitario, descuento_linea=l.descuento_linea,
                    impuesto_tasa=l.impuesto_tasa, producto_unidad_id=l.producto_unidad_id,
                ) for l in pedido.lineas
            ]
            if con_envio:
                entrada.lineas.append(LineaInput(
                    producto_id=self._producto_envio_id, cantidad=Decimal("1"),
                    precio_unitario=pedido.costo_envio,
                ))
            entrada.puede_descuento_manual = data.puede_descuento_manual
            entrada.rol_id = data.rol_id
        else:
            # Precio congelado del pedido: se respeta la cotización tal cual. El
            # descuento manual ya fue autorizado al crear/confirmar el pedido.
            congeladas = [
                DetalleVenta.crear(
                    producto_id=l.producto_id, cantidad=l.cantidad,
                    precio_unitario=l.precio_unitario, descuento_linea=l.descuento_linea,
                    impuesto_tasa=l.impuesto_tasa, producto_unidad_id=l.producto_unidad_id,
                    cantidad_en_unidad_base=l.cantidad_en_unidad_base,
                    promo_id=l.promo_id, promo_etiqueta=l.promo_etiqueta,
                    promo_descuento=l.promo_descuento,
                ) for l in pedido.lineas
            ]
            if con_envio:
                congeladas.append(DetalleVenta.crear(
                    producto_id=self._producto_envio_id, cantidad=Decimal("1"),
                    precio_unitario=pedido.costo_envio,
                    cantidad_en_unidad_base=Decimal("1"),
                ))
            entrada.lineas_congeladas = congeladas
            entrada.puede_descuento_manual = True
            entrada.rol_id = None

        venta = await self._venta_uc.ejecutar(entrada)
        pedido.marcar_facturado(venta.id)
        await self._repo.actualizar(pedido)
        await self._event_port.publicar("PedidoFacturado", {
            "usuario_id": data.usuario_id, "modulo": "pedidos", "accion": "facturar_pedido",
            "entidad": "Pedido", "entidad_id": str(pedido.id),
            "detalle": {
                "pedido_id": str(pedido.id), "venta_id": str(venta.id),
                "total": str(venta.total), "recalculo": data.recalcular_precios,
            },
        })
        return venta
