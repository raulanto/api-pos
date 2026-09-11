from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import List
from uuid import UUID

from app.modules.ventas.application.use_cases.crear_venta import (
    CrearVentaUseCase, CotizarVentaInput, LineaInput,
)
from app.modules.ventas.application.ports.event_port import EventPort
from app.modules.usuarios.application.ports.usuario_repository import UsuarioRepository
from app.modules.pedidos.application.ports.pedido_repository import PedidoRepository
from app.modules.pedidos.domain.entities import Pedido, DetallePedido
from app.modules.pedidos.domain.exceptions import ResponsableInvalido
from app.modules.pedidos.domain.value_objects import TipoPedido, CanalPedido


@dataclass
class LineaPedidoInput:
    producto_id: UUID
    cantidad: Decimal
    precio_unitario: Decimal
    descuento_linea: Decimal = Decimal("0")
    impuesto_tasa: Decimal = Decimal("0")
    producto_unidad_id: UUID | None = None
    asignado_a: UUID | None = None      # responsable si la línea es un servicio


@dataclass
class CrearPedidoInput:
    sucursal_id: UUID
    usuario_id: UUID
    tipo: TipoPedido
    canal: CanalPedido
    lineas: List[LineaPedidoInput]
    cliente_id: UUID | None = None
    telefono: str | None = None
    descuento_total: Decimal = Decimal("0")
    motivo_descuento: str | None = None
    codigo_cupon: str | None = None
    cliente_segmento: str | None = None
    notas: str | None = None
    fecha_promesa: datetime | None = None
    direccion_texto: str | None = None
    referencia_direccion: str | None = None
    idempotency_key: str | None = None
    confirmar: bool = False   # crear directamente en estado `confirmado`


def _cotizar_input(data) -> CotizarVentaInput:
    return CotizarVentaInput(
        sucursal_id=data.sucursal_id,
        lineas=[
            LineaInput(
                producto_id=l.producto_id, cantidad=l.cantidad,
                precio_unitario=l.precio_unitario, descuento_linea=l.descuento_linea,
                impuesto_tasa=l.impuesto_tasa, producto_unidad_id=l.producto_unidad_id,
            ) for l in data.lineas
        ],
        descuento_total=data.descuento_total,
        cliente_segmento=data.cliente_segmento,
        codigo_cupon=data.codigo_cupon,
        telefono=data.telefono,
    )


async def cotizar_a_detalles(
    crear_venta_uc: CrearVentaUseCase, data
) -> list[DetallePedido]:
    """Corre el motor de precios de ventas (mayoreo + promociones + unidad base,
    valida producto/presentación) SIN tocar stock ni persistir, y devuelve las
    líneas ya congeladas como `DetallePedido`. Marca `es_servicio` (lo dice la
    cotización) y arrastra `asignado_a` de la línea de entrada por posición."""
    cot = await crear_venta_uc.cotizar(_cotizar_input(data))
    out: list[DetallePedido] = []
    for i, c in enumerate(cot.lineas):
        asignado_a = data.lineas[i].asignado_a if i < len(data.lineas) else None
        out.append(DetallePedido.crear(
            producto_id=c.producto_id, cantidad=c.cantidad,
            precio_unitario=c.precio_unitario, descuento_linea=c.descuento_linea,
            impuesto_tasa=c.impuesto_tasa, producto_unidad_id=c.producto_unidad_id,
            cantidad_en_unidad_base=c.cantidad_en_unidad_base,
            promo_id=c.promo_id, promo_etiqueta=c.promo_etiqueta,
            promo_descuento=c.promo_descuento,
            es_servicio=c.es_servicio,
            asignado_a=asignado_a if c.es_servicio else None,
        ))
    return out


async def validar_responsables(
    usuario_repo: UsuarioRepository, detalles: list[DetallePedido]
) -> None:
    """Cada `asignado_a` presente debe ser un usuario activo."""
    ids = {l.asignado_a for l in detalles if l.asignado_a is not None}
    for uid in ids:
        u = await usuario_repo.obtener_por_id(uid)
        if u is None or not getattr(u, "activo", True):
            raise ResponsableInvalido(
                f"El responsable {uid} no existe o no está activo."
            )


class CrearPedidoUseCase:
    def __init__(
        self, pedido_repo: PedidoRepository, crear_venta_uc: CrearVentaUseCase,
        event_port: EventPort, usuario_repo: UsuarioRepository,
    ):
        self._repo = pedido_repo
        self._venta_uc = crear_venta_uc
        self._event_port = event_port
        self._usuario_repo = usuario_repo

    async def ejecutar(self, data: CrearPedidoInput) -> Pedido:
        if data.idempotency_key:
            previa = await self._repo.obtener_por_idempotency_key(data.idempotency_key)
            if previa is not None:
                return previa

        lineas = await cotizar_a_detalles(self._venta_uc, data)
        await validar_responsables(self._usuario_repo, lineas)
        pedido = Pedido.crear(
            sucursal_id=data.sucursal_id, usuario_id=data.usuario_id,
            tipo=data.tipo, canal=data.canal, lineas=lineas,
            cliente_id=data.cliente_id, telefono=data.telefono,
            descuento_total=data.descuento_total, motivo_descuento=data.motivo_descuento,
            codigo_cupon=data.codigo_cupon,
            cliente_segmento=data.cliente_segmento, notas=data.notas,
            fecha_promesa=data.fecha_promesa,
            direccion_texto=data.direccion_texto,
            referencia_direccion=data.referencia_direccion,
            idempotency_key=data.idempotency_key,
        )
        if data.confirmar:
            pedido.confirmar()

        await self._repo.guardar(pedido)
        await self._event_port.publicar("PedidoCreado", {
            "usuario_id": data.usuario_id,
            "modulo": "pedidos",
            "accion": "crear_pedido",
            "entidad": "Pedido",
            "entidad_id": str(pedido.id),
            "detalle": {
                "pedido_id": str(pedido.id),
                "sucursal_id": str(pedido.sucursal_id),
                "tipo": pedido.tipo.value,
                "canal": pedido.canal.value,
                "estado": pedido.estado.value,
                "total": str(pedido.total),
            },
        })
        return pedido
