from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from app.modules.ventas.domain.value_objects import MetodoPago
from app.modules.pedidos.domain.value_objects import (
    TipoPedido, CanalPedido, EstadoPedido, EstadoEntrega, TRANSICIONES_ENTREGA,
)
from app.modules.pedidos.domain.exceptions import (
    PedidoSinLineas, TransicionPedidoInvalida, PedidoNoEditable, PedidoYaFacturado,
    DireccionEnvioRequerida, EntregaNoAplica, AnticipoInvalido,
    MotivoDescuentoRequerido, ServicioSinResponsable, ResponsableInvalido,
)


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class DetallePedido:
    """Línea de un pedido. Mismos campos congelables que `DetalleVenta` de ventas
    (el precio ya trae mayoreo/promoción resueltos por el motor de ventas)."""
    id: UUID
    pedido_id: UUID
    producto_id: UUID
    cantidad: Decimal
    precio_unitario: Decimal
    descuento_linea: Decimal = Decimal("0")
    impuesto_tasa: Decimal = Decimal("0")
    producto_unidad_id: UUID | None = None
    cantidad_en_unidad_base: Decimal | None = None
    promo_id: UUID | None = None
    promo_etiqueta: str | None = None
    promo_descuento: Decimal = Decimal("0")
    # Congelado por el backend según el `tipo` del producto (servicio = no mueve
    # stock). Una línea `es_servicio` necesita `asignado_a` para confirmar.
    es_servicio: bool = False
    asignado_a: UUID | None = None      # usuario responsable del servicio

    @staticmethod
    def crear(
        producto_id: UUID, cantidad: Decimal, precio_unitario: Decimal,
        descuento_linea: Decimal = Decimal("0"), impuesto_tasa: Decimal = Decimal("0"),
        producto_unidad_id: UUID | None = None,
        cantidad_en_unidad_base: Decimal | None = None,
        promo_id: UUID | None = None, promo_etiqueta: str | None = None,
        promo_descuento: Decimal = Decimal("0"),
        es_servicio: bool = False, asignado_a: UUID | None = None,
    ) -> "DetallePedido":
        return DetallePedido(
            id=uuid4(), pedido_id=uuid4(),
            producto_id=producto_id, cantidad=cantidad, precio_unitario=precio_unitario,
            descuento_linea=descuento_linea, impuesto_tasa=impuesto_tasa,
            producto_unidad_id=producto_unidad_id,
            cantidad_en_unidad_base=cantidad_en_unidad_base,
            promo_id=promo_id, promo_etiqueta=promo_etiqueta,
            promo_descuento=promo_descuento,
            es_servicio=es_servicio, asignado_a=asignado_a,
        )

    @property
    def subtotal(self) -> Decimal:
        return (self.cantidad * self.precio_unitario) - self.descuento_linea - self.promo_descuento


@dataclass
class PedidoPago:
    """Anticipo / pago adelantado de un pedido (prepago online, tarjeta, etc.).
    Al facturar entra como un `Pago` de la venta; al cancelar se marca
    `reembolsado` y se emite un evento para devolver el dinero fuera de banda."""
    id: UUID
    pedido_id: UUID
    monto: Decimal
    metodo_pago: MetodoPago
    referencia: str | None = None
    reembolsado: bool = False
    created_at: datetime = field(default_factory=_ahora)

    @staticmethod
    def crear(monto: Decimal, metodo_pago: MetodoPago,
              referencia: str | None = None) -> "PedidoPago":
        if monto <= 0:
            raise AnticipoInvalido("El anticipo debe ser mayor a 0.")
        if metodo_pago == MetodoPago.CREDITO:
            raise AnticipoInvalido("Un anticipo no puede ser a crédito.")
        return PedidoPago(
            id=uuid4(), pedido_id=uuid4(), monto=monto, metodo_pago=metodo_pago,
            referencia=(referencia.strip() if referencia and referencia.strip() else None),
        )


@dataclass
class Pedido:
    id: UUID
    sucursal_id: UUID
    usuario_id: UUID           # quien creó el pedido
    tipo: TipoPedido
    canal: CanalPedido
    estado: EstadoPedido
    cliente_id: UUID | None = None
    telefono: str | None = None
    descuento_total: Decimal = Decimal("0")
    motivo_descuento: str | None = None
    codigo_cupon: str | None = None
    cliente_segmento: str | None = None   # hint para promos por segmento
    notas: str | None = None
    fecha_promesa: datetime | None = None

    # --- Entrega (sólo domicilio/recoger) ---
    estado_entrega: EstadoEntrega | None = None
    direccion_texto: str | None = None
    referencia_direccion: str | None = None
    repartidor_id: UUID | None = None
    entrega_fallo_motivo: str | None = None
    despachado_en: datetime | None = None
    entregado_en: datetime | None = None

    # --- Cierre ---
    venta_id: UUID | None = None
    idempotency_key: str | None = None
    created_at: datetime = field(default_factory=_ahora)

    lineas: list[DetallePedido] = field(default_factory=list)
    pagos: list[PedidoPago] = field(default_factory=list)

    # Relaciones embebidas opcionales (`?include=`); las puebla el mapper.
    cliente: object | None = field(default=None, compare=False, repr=False)
    repartidor: object | None = field(default=None, compare=False, repr=False)

    # ------------------------------------------------------------------ #
    @staticmethod
    def crear(
        sucursal_id: UUID, usuario_id: UUID, tipo: TipoPedido, canal: CanalPedido,
        lineas: list[DetallePedido], *,
        cliente_id: UUID | None = None, telefono: str | None = None,
        descuento_total: Decimal = Decimal("0"), motivo_descuento: str | None = None,
        codigo_cupon: str | None = None,
        cliente_segmento: str | None = None, notas: str | None = None,
        fecha_promesa: datetime | None = None,
        direccion_texto: str | None = None, referencia_direccion: str | None = None,
        idempotency_key: str | None = None,
    ) -> "Pedido":
        if not lineas:
            raise PedidoSinLineas("Un pedido necesita al menos una línea.")

        pedido_id = uuid4()
        for l in lineas:
            l.pedido_id = pedido_id

        direccion_texto = (direccion_texto or "").strip() or None
        if tipo == TipoPedido.DOMICILIO and not direccion_texto:
            raise DireccionEnvioRequerida(
                "Un pedido a domicilio necesita `direccion_texto`."
            )

        motivo_descuento = (motivo_descuento or "").strip() or None
        hay_manual = descuento_total > 0 or any(l.descuento_linea > 0 for l in lineas)
        if hay_manual and not motivo_descuento:
            raise MotivoDescuentoRequerido(
                "El descuento manual del pedido requiere `motivo_descuento`."
            )

        return Pedido(
            id=pedido_id, sucursal_id=sucursal_id, usuario_id=usuario_id,
            tipo=tipo, canal=canal, estado=EstadoPedido.BORRADOR,
            cliente_id=cliente_id, telefono=(telefono or "").strip() or None,
            descuento_total=descuento_total, motivo_descuento=motivo_descuento,
            codigo_cupon=(codigo_cupon or "").strip() or None,
            cliente_segmento=cliente_segmento, notas=(notas or "").strip() or None,
            fecha_promesa=fecha_promesa,
            estado_entrega=(
                EstadoEntrega.PENDIENTE
                if tipo in (TipoPedido.DOMICILIO, TipoPedido.RECOGER) else None
            ),
            direccion_texto=direccion_texto,
            referencia_direccion=(referencia_direccion or "").strip() or None,
            idempotency_key=idempotency_key, lineas=lineas,
        )

    # ------------------------------------------------------------------ #
    @property
    def editable(self) -> bool:
        return self.estado == EstadoPedido.BORRADOR

    @property
    def subtotal(self) -> Decimal:
        return sum((l.subtotal for l in self.lineas), Decimal("0"))

    @property
    def total(self) -> Decimal:
        return self.subtotal - self.descuento_total

    @property
    def servicios_sin_responsable(self) -> list[DetallePedido]:
        return [l for l in self.lineas if l.es_servicio and l.asignado_a is None]

    @property
    def total_promociones(self) -> Decimal:
        return sum((l.promo_descuento for l in self.lineas), Decimal("0"))

    @property
    def total_anticipos(self) -> Decimal:
        return sum((p.monto for p in self.pagos if not p.reembolsado), Decimal("0"))

    @property
    def saldo_por_cobrar(self) -> Decimal:
        return self.total - self.total_anticipos

    # ------------------------------------------------------------------ #
    def reemplazar_lineas(self, lineas: list[DetallePedido]) -> None:
        if not self.editable:
            raise PedidoNoEditable(f"El pedido {self.id} no está en borrador.")
        if not lineas:
            raise PedidoSinLineas("Un pedido necesita al menos una línea.")
        for l in lineas:
            l.pedido_id = self.id
        self.lineas = lineas

    def cambiar_tipo(self, nuevo: TipoPedido) -> None:
        """Cambia el tipo (sólo en borrador) y reajusta la entrega:
        - a `mostrador`: sin entrega ni datos de envío;
        - a `domicilio`/`recoger`: arranca la entrega en `pendiente` si no tenía."""
        if not self.editable:
            raise PedidoNoEditable(f"El pedido {self.id} no está en borrador.")
        self.tipo = nuevo
        if nuevo == TipoPedido.MOSTRADOR:
            self.estado_entrega = None
            self.direccion_texto = None
            self.referencia_direccion = None
            self.repartidor_id = None
            self.entrega_fallo_motivo = None
            self.despachado_en = None
            self.entregado_en = None
        elif self.estado_entrega is None:
            self.estado_entrega = EstadoEntrega.PENDIENTE

    def asignar_servicio(self, detalle_id: UUID, usuario_id: UUID) -> None:
        """Fija el responsable de una línea de servicio. Vale en borrador y
        confirmado (reasignar un repartidor/técnico); no en facturado/cancelado."""
        if self.estado in (EstadoPedido.FACTURADO, EstadoPedido.CANCELADO):
            raise TransicionPedidoInvalida(
                f"No se reasignan servicios en un pedido '{self.estado.value}'."
            )
        linea = next((l for l in self.lineas if l.id == detalle_id), None)
        if linea is None:
            raise ResponsableInvalido(
                f"La línea {detalle_id} no pertenece al pedido {self.id}."
            )
        if not linea.es_servicio:
            raise ResponsableInvalido("La línea no es un servicio.")
        linea.asignado_a = usuario_id

    def confirmar(self) -> None:
        if self.estado != EstadoPedido.BORRADOR:
            raise TransicionPedidoInvalida(
                f"Sólo se confirma un pedido en borrador (está '{self.estado.value}')."
            )
        if self.tipo == TipoPedido.DOMICILIO and not self.direccion_texto:
            raise DireccionEnvioRequerida(
                "Un pedido a domicilio necesita `direccion_texto` antes de confirmar."
            )
        faltan = self.servicios_sin_responsable
        if faltan:
            raise ServicioSinResponsable(
                f"{len(faltan)} línea(s) de servicio sin persona asignada "
                "(`asignado_a`)."
            )
        self.estado = EstadoPedido.CONFIRMADO

    def reabrir(self) -> None:
        if self.estado != EstadoPedido.CONFIRMADO:
            raise TransicionPedidoInvalida(
                f"Sólo se reabre un pedido confirmado (está '{self.estado.value}')."
            )
        self.estado = EstadoPedido.BORRADOR

    def cancelar(self) -> None:
        if self.estado == EstadoPedido.FACTURADO:
            raise PedidoYaFacturado(
                f"El pedido {self.id} ya está facturado; anulá la venta {self.venta_id}."
            )
        if self.estado == EstadoPedido.CANCELADO:
            raise TransicionPedidoInvalida(f"El pedido {self.id} ya está cancelado.")
        self.estado = EstadoPedido.CANCELADO

    def marcar_facturado(self, venta_id: UUID) -> None:
        if self.estado != EstadoPedido.CONFIRMADO:
            raise TransicionPedidoInvalida(
                f"Sólo se factura un pedido confirmado (está '{self.estado.value}')."
            )
        self.venta_id = venta_id
        self.estado = EstadoPedido.FACTURADO

    def agregar_anticipo(self, pago: PedidoPago) -> None:
        if self.estado in (EstadoPedido.FACTURADO, EstadoPedido.CANCELADO):
            raise TransicionPedidoInvalida(
                f"No se registran anticipos en un pedido '{self.estado.value}'."
            )
        pago.pedido_id = self.id
        self.pagos.append(pago)

    def marcar_anticipos_reembolsados(self) -> list[PedidoPago]:
        """Marca como reembolsados los anticipos vivos. Devuelve los afectados."""
        afectados = [p for p in self.pagos if not p.reembolsado]
        for p in afectados:
            p.reembolsado = True
        return afectados

    # --- Entrega ---
    def asignar_repartidor(self, repartidor_id: UUID) -> None:
        if self.estado_entrega is None:
            raise EntregaNoAplica(
                f"El pedido {self.id} ({self.tipo.value}) no tiene entrega."
            )
        self.repartidor_id = repartidor_id

    def avanzar_entrega(self, nuevo: EstadoEntrega, *, motivo: str | None = None,
                        ahora: datetime | None = None) -> None:
        if self.estado_entrega is None:
            raise EntregaNoAplica(
                f"El pedido {self.id} ({self.tipo.value}) no tiene entrega."
            )
        permitidos = TRANSICIONES_ENTREGA.get(self.estado_entrega, set())
        if nuevo not in permitidos:
            raise TransicionPedidoInvalida(
                f"Entrega: no se puede pasar de '{self.estado_entrega.value}' a "
                f"'{nuevo.value}'."
            )
        motivo = (motivo or "").strip() or None
        if nuevo == EstadoEntrega.FALLIDO and not motivo:
            raise TransicionPedidoInvalida(
                "Una entrega fallida necesita `motivo`."
            )
        ahora = ahora or _ahora()
        if nuevo == EstadoEntrega.EN_REPARTO and self.despachado_en is None:
            self.despachado_en = ahora
        if nuevo == EstadoEntrega.ENTREGADO:
            self.entregado_en = ahora
        self.entrega_fallo_motivo = motivo if nuevo == EstadoEntrega.FALLIDO else None
        self.estado_entrega = nuevo
