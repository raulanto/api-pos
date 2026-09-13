from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from app.modules.proveedores.domain.value_objects import (
    TipoPersona, CondicionesPago, EstadoPedidoProveedor, EstadoRecepcion,
    MotivoDefecto, AccionDefecto, EstadoDevolucionProveedor, ResultadoDevolucion,
    TipoResolucionDevolucion,
)
from app.modules.proveedores.domain.exceptions import (
    DiasCreditoRequerido, PedidoProveedorSinLineas, PedidoNoEditable,
    TransicionPedidoProveedorInvalida, RecepcionSinLineas, DefectoInvalido,
    TransicionDevolucionInvalida,
)


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


def _folio(entity_id: UUID) -> str:
    """Folio corto no persistido, derivado del id (mismo patrón que el
    `folio` del ticket de venta: `str(id)[:8]`)."""
    return str(entity_id)[:8].upper()


# --------------------------------------------------------------------------- #
# Proveedor
# --------------------------------------------------------------------------- #
@dataclass
class Proveedor:
    id: UUID
    codigo: str
    razon_social: str
    tipo_persona: TipoPersona
    condiciones_pago: CondicionesPago
    dias_credito: int | None = None
    nombre_comercial: str | None = None
    rfc: str | None = None
    moneda: str = "MXN"
    contacto_principal: str | None = None
    telefono: str | None = None
    email: str | None = None
    direccion_calle: str | None = None
    direccion_numero: str | None = None
    direccion_colonia: str | None = None
    direccion_ciudad: str | None = None
    direccion_estado: str | None = None
    direccion_codigo_postal: str | None = None
    activo: bool = True
    notas: str | None = None
    created_at: datetime = field(default_factory=_ahora)
    updated_at: datetime | None = None

    @staticmethod
    def crear(
        codigo: str, razon_social: str, tipo_persona: TipoPersona,
        condiciones_pago: CondicionesPago, dias_credito: int | None = None,
        **kw,
    ) -> "Proveedor":
        codigo = (codigo or "").strip()
        razon_social = (razon_social or "").strip()
        if not codigo or not razon_social:
            raise ValueError("El proveedor necesita `codigo` y `razon_social`.")
        if condiciones_pago == CondicionesPago.CREDITO:
            if not dias_credito or dias_credito <= 0:
                raise DiasCreditoRequerido(
                    "`condiciones_pago=credito` necesita `dias_credito` > 0."
                )
        else:
            dias_credito = None
        return Proveedor(
            id=uuid4(), codigo=codigo, razon_social=razon_social,
            tipo_persona=tipo_persona, condiciones_pago=condiciones_pago,
            dias_credito=dias_credito, **kw,
        )

    def actualizar(
        self, *, razon_social: str | None = None, tipo_persona: TipoPersona | None = None,
        condiciones_pago: CondicionesPago | None = None, dias_credito: int | None = None,
        cambiar_dias_credito: bool = False, moneda: str | None = None,
        nombre_comercial: str | None = None, cambiar_nombre_comercial: bool = False,
        rfc: str | None = None, cambiar_rfc: bool = False,
        contacto_principal: str | None = None, cambiar_contacto_principal: bool = False,
        telefono: str | None = None, cambiar_telefono: bool = False,
        email: str | None = None, cambiar_email: bool = False,
        notas: str | None = None, cambiar_notas: bool = False,
        **direccion,
    ) -> None:
        if razon_social is not None:
            self.razon_social = razon_social.strip()
        if tipo_persona is not None:
            self.tipo_persona = tipo_persona
        nuevas_condiciones = condiciones_pago or self.condiciones_pago
        if condiciones_pago is not None:
            self.condiciones_pago = condiciones_pago
        if cambiar_dias_credito:
            self.dias_credito = dias_credito
        elif dias_credito is not None:
            self.dias_credito = dias_credito
        if nuevas_condiciones == CondicionesPago.CREDITO:
            if not self.dias_credito or self.dias_credito <= 0:
                raise DiasCreditoRequerido(
                    "`condiciones_pago=credito` necesita `dias_credito` > 0."
                )
        else:
            self.dias_credito = None
        if moneda is not None:
            self.moneda = moneda
        if cambiar_nombre_comercial:
            self.nombre_comercial = nombre_comercial
        elif nombre_comercial is not None:
            self.nombre_comercial = nombre_comercial
        if cambiar_rfc:
            self.rfc = rfc
        elif rfc is not None:
            self.rfc = rfc
        if cambiar_contacto_principal:
            self.contacto_principal = contacto_principal
        elif contacto_principal is not None:
            self.contacto_principal = contacto_principal
        if cambiar_telefono:
            self.telefono = telefono
        elif telefono is not None:
            self.telefono = telefono
        if cambiar_email:
            self.email = email
        elif email is not None:
            self.email = email
        if cambiar_notas:
            self.notas = notas
        elif notas is not None:
            self.notas = notas
        for campo, valor in direccion.items():
            if hasattr(self, campo) and valor is not None:
                setattr(self, campo, valor)

    def desactivar(self) -> None:
        self.activo = False

    def activar(self) -> None:
        self.activo = True


# --------------------------------------------------------------------------- #
# ProductoProveedor
# --------------------------------------------------------------------------- #
@dataclass
class ProductoProveedor:
    id: UUID
    producto_id: UUID
    proveedor_id: UUID
    precio_compra: Decimal
    tiempo_entrega_dias: int
    stock_minimo: Decimal
    cantidad_reorden: Decimal
    codigo_proveedor: str | None = None
    stock_maximo: Decimal | None = None
    es_proveedor_principal: bool = False
    activo: bool = True
    created_at: datetime = field(default_factory=_ahora)

    @staticmethod
    def crear(
        producto_id: UUID, proveedor_id: UUID, precio_compra: Decimal,
        tiempo_entrega_dias: int, stock_minimo: Decimal, cantidad_reorden: Decimal,
        codigo_proveedor: str | None = None, stock_maximo: Decimal | None = None,
        es_proveedor_principal: bool = False,
    ) -> "ProductoProveedor":
        if precio_compra < 0:
            raise ValueError("`precio_compra` no puede ser negativo.")
        if tiempo_entrega_dias < 0:
            raise ValueError("`tiempo_entrega_dias` no puede ser negativo.")
        if stock_minimo < 0:
            raise ValueError("`stock_minimo` no puede ser negativo.")
        if cantidad_reorden <= 0:
            raise ValueError("`cantidad_reorden` debe ser mayor a 0.")
        if stock_maximo is not None and stock_maximo < stock_minimo:
            raise ValueError("`stock_maximo` no puede ser menor a `stock_minimo`.")
        return ProductoProveedor(
            id=uuid4(), producto_id=producto_id, proveedor_id=proveedor_id,
            precio_compra=precio_compra, tiempo_entrega_dias=tiempo_entrega_dias,
            stock_minimo=stock_minimo, cantidad_reorden=cantidad_reorden,
            codigo_proveedor=(codigo_proveedor or "").strip() or None,
            stock_maximo=stock_maximo, es_proveedor_principal=es_proveedor_principal,
        )

    def marcar_principal(self) -> None:
        self.es_proveedor_principal = True

    def quitar_principal(self) -> None:
        self.es_proveedor_principal = False

    def desactivar(self) -> None:
        self.activo = False
        self.es_proveedor_principal = False

    def reactivar(self) -> None:
        self.activo = True


# --------------------------------------------------------------------------- #
# Pedido a proveedor (orden de compra)
# --------------------------------------------------------------------------- #
@dataclass
class PedidoProveedorLinea:
    id: UUID
    pedido_id: UUID
    producto_id: UUID
    cantidad_solicitada: Decimal
    precio_unitario: Decimal
    cantidad_recibida: Decimal = Decimal("0")

    @staticmethod
    def crear(
        producto_id: UUID, cantidad_solicitada: Decimal, precio_unitario: Decimal,
    ) -> "PedidoProveedorLinea":
        if cantidad_solicitada <= 0:
            raise ValueError("`cantidad_solicitada` debe ser mayor a 0.")
        if precio_unitario < 0:
            raise ValueError("`precio_unitario` no puede ser negativo.")
        return PedidoProveedorLinea(
            id=uuid4(), pedido_id=uuid4(), producto_id=producto_id,
            cantidad_solicitada=cantidad_solicitada, precio_unitario=precio_unitario,
        )

    @property
    def subtotal(self) -> Decimal:
        return self.cantidad_solicitada * self.precio_unitario

    @property
    def pendiente(self) -> Decimal:
        return self.cantidad_solicitada - self.cantidad_recibida


@dataclass
class PedidoProveedor:
    id: UUID
    proveedor_id: UUID
    sucursal_id: UUID
    estado: EstadoPedidoProveedor
    fecha_pedido: datetime
    generado_automaticamente: bool = False
    generado_por: UUID | None = None
    confirmado_por: UUID | None = None
    fecha_estimada_entrega: date | None = None
    notas: str | None = None
    created_at: datetime = field(default_factory=_ahora)
    lineas: list[PedidoProveedorLinea] = field(default_factory=list)

    proveedor: object | None = field(default=None, compare=False, repr=False)

    @staticmethod
    def crear(
        proveedor_id: UUID, sucursal_id: UUID, lineas: list[PedidoProveedorLinea],
        generado_automaticamente: bool = False, generado_por: UUID | None = None,
        fecha_estimada_entrega: date | None = None, notas: str | None = None,
    ) -> "PedidoProveedor":
        if not lineas:
            raise PedidoProveedorSinLineas("Un pedido necesita al menos una línea.")
        pedido_id = uuid4()
        for l in lineas:
            l.pedido_id = pedido_id
        return PedidoProveedor(
            id=pedido_id, proveedor_id=proveedor_id, sucursal_id=sucursal_id,
            estado=EstadoPedidoProveedor.BORRADOR, fecha_pedido=_ahora(),
            generado_automaticamente=generado_automaticamente, generado_por=generado_por,
            fecha_estimada_entrega=fecha_estimada_entrega, notas=notas, lineas=lineas,
        )

    @property
    def folio(self) -> str:
        return f"OC-{_folio(self.id)}"

    @property
    def subtotal(self) -> Decimal:
        return sum((l.subtotal for l in self.lineas), Decimal("0"))

    @property
    def editable(self) -> bool:
        return self.estado == EstadoPedidoProveedor.BORRADOR

    def agregar_lineas(self, nuevas: list[PedidoProveedorLinea]) -> None:
        """El motor de reorden suma líneas a un borrador ya abierto en vez de
        crear un pedido nuevo por cada corrida."""
        if not self.editable:
            raise PedidoNoEditable(f"El pedido {self.id} no está en borrador.")
        for l in nuevas:
            l.pedido_id = self.id
            existente = next((x for x in self.lineas if x.producto_id == l.producto_id), None)
            if existente is not None:
                existente.cantidad_solicitada += l.cantidad_solicitada
            else:
                self.lineas.append(l)

    def confirmar_envio(self, usuario_id: UUID) -> None:
        if self.estado != EstadoPedidoProveedor.BORRADOR:
            raise TransicionPedidoProveedorInvalida(
                f"Sólo se confirma el envío de un pedido en borrador (está "
                f"'{self.estado.value}')."
            )
        self.estado = EstadoPedidoProveedor.ENVIADO
        self.confirmado_por = usuario_id

    def cancelar(self) -> None:
        if self.estado in (EstadoPedidoProveedor.RECIBIDO, EstadoPedidoProveedor.CANCELADO):
            raise TransicionPedidoProveedorInvalida(
                f"El pedido {self.id} está '{self.estado.value}': no se puede cancelar."
            )
        self.estado = EstadoPedidoProveedor.CANCELADO

    def registrar_recepcion_parcial(self, por_producto: dict[UUID, Decimal]) -> None:
        """Suma lo recibido a cada línea y recalcula el estado. Llamado desde
        `RegistrarRecepcionUseCase` cuando la recepción trae `pedido_id`."""
        if self.estado not in (
            EstadoPedidoProveedor.ENVIADO, EstadoPedidoProveedor.CONFIRMADO,
            EstadoPedidoProveedor.PARCIAL,
        ):
            raise TransicionPedidoProveedorInvalida(
                f"No se puede recibir mercancía de un pedido '{self.estado.value}'."
            )
        for linea in self.lineas:
            recibido = por_producto.get(linea.producto_id)
            if recibido:
                linea.cantidad_recibida += recibido
        if all(l.cantidad_recibida >= l.cantidad_solicitada for l in self.lineas):
            self.estado = EstadoPedidoProveedor.RECIBIDO
        else:
            self.estado = EstadoPedidoProveedor.PARCIAL


# --------------------------------------------------------------------------- #
# Recepción de mercancía (evento inmutable)
# --------------------------------------------------------------------------- #
@dataclass
class RecepcionProveedorLinea:
    id: UUID
    recepcion_id: UUID
    producto_id: UUID
    cantidad_recibida_buena: Decimal
    cantidad_defectuosa: Decimal = Decimal("0")
    cantidad_esperada: Decimal | None = None
    motivo_defecto: MotivoDefecto | None = None
    accion_defecto: AccionDefecto | None = None
    fotos_evidencia_keys: list[str] = field(default_factory=list)
    notas: str | None = None

    @staticmethod
    def crear(
        producto_id: UUID, cantidad_recibida_buena: Decimal,
        cantidad_defectuosa: Decimal = Decimal("0"), cantidad_esperada: Decimal | None = None,
        motivo_defecto: MotivoDefecto | None = None, accion_defecto: AccionDefecto | None = None,
        fotos_evidencia_keys: list[str] | None = None, notas: str | None = None,
    ) -> "RecepcionProveedorLinea":
        if cantidad_recibida_buena < 0 or cantidad_defectuosa < 0:
            raise ValueError("Las cantidades no pueden ser negativas.")
        if cantidad_recibida_buena == 0 and cantidad_defectuosa == 0:
            raise ValueError("La línea necesita alguna cantidad recibida (buena o defectuosa).")
        if cantidad_defectuosa > 0:
            if motivo_defecto is None or accion_defecto is None:
                raise DefectoInvalido(
                    "Una línea con `cantidad_defectuosa` > 0 necesita `motivo_defecto` "
                    "y `accion_defecto`."
                )
        elif motivo_defecto is not None or accion_defecto is not None:
            raise DefectoInvalido(
                "`motivo_defecto`/`accion_defecto` sólo aplican si hay `cantidad_defectuosa`."
            )
        return RecepcionProveedorLinea(
            id=uuid4(), recepcion_id=uuid4(), producto_id=producto_id,
            cantidad_recibida_buena=cantidad_recibida_buena,
            cantidad_defectuosa=cantidad_defectuosa, cantidad_esperada=cantidad_esperada,
            motivo_defecto=motivo_defecto, accion_defecto=accion_defecto,
            fotos_evidencia_keys=fotos_evidencia_keys or [], notas=notas,
        )

    @property
    def cantidad_total(self) -> Decimal:
        return self.cantidad_recibida_buena + self.cantidad_defectuosa


@dataclass
class RecepcionProveedor:
    id: UUID
    proveedor_id: UUID
    sucursal_id: UUID
    recibido_por: UUID
    fecha_recepcion: datetime
    estado: EstadoRecepcion
    lineas: list[RecepcionProveedorLinea]
    pedido_id: UUID | None = None
    numero_factura: str | None = None
    numero_remision: str | None = None
    transportista: str | None = None
    notas: str | None = None
    created_at: datetime = field(default_factory=_ahora)

    @staticmethod
    def crear(
        proveedor_id: UUID, sucursal_id: UUID, recibido_por: UUID,
        lineas: list[RecepcionProveedorLinea], pedido_id: UUID | None = None,
        numero_factura: str | None = None, numero_remision: str | None = None,
        transportista: str | None = None, notas: str | None = None,
    ) -> "RecepcionProveedor":
        if not lineas:
            raise RecepcionSinLineas("Una recepción necesita al menos una línea.")
        recepcion_id = uuid4()
        for l in lineas:
            l.recepcion_id = recepcion_id
        if any(l.cantidad_defectuosa > 0 for l in lineas):
            estado = EstadoRecepcion.CON_DEFECTOS
        elif any(
            l.cantidad_esperada is not None and l.cantidad_total < l.cantidad_esperada
            for l in lineas
        ):
            estado = EstadoRecepcion.PARCIAL
        else:
            estado = EstadoRecepcion.COMPLETA
        return RecepcionProveedor(
            id=recepcion_id, proveedor_id=proveedor_id, sucursal_id=sucursal_id,
            recibido_por=recibido_por, fecha_recepcion=_ahora(), estado=estado,
            lineas=lineas, pedido_id=pedido_id, numero_factura=numero_factura,
            numero_remision=numero_remision, transportista=transportista, notas=notas,
        )

    @property
    def folio(self) -> str:
        return f"REC-{_folio(self.id)}"


# --------------------------------------------------------------------------- #
# Devolución a proveedor
# --------------------------------------------------------------------------- #
@dataclass
class DevolucionProveedorLinea:
    id: UUID
    devolucion_id: UUID
    recepcion_detalle_id: UUID
    producto_id: UUID
    cantidad: Decimal

    @staticmethod
    def crear(
        recepcion_detalle_id: UUID, producto_id: UUID, cantidad: Decimal,
    ) -> "DevolucionProveedorLinea":
        if cantidad <= 0:
            raise ValueError("`cantidad` debe ser mayor a 0.")
        return DevolucionProveedorLinea(
            id=uuid4(), devolucion_id=uuid4(), recepcion_detalle_id=recepcion_detalle_id,
            producto_id=producto_id, cantidad=cantidad,
        )


@dataclass
class DevolucionProveedor:
    id: UUID
    proveedor_id: UUID
    recepcion_id: UUID
    creado_por: UUID
    estado: EstadoDevolucionProveedor
    lineas: list[DevolucionProveedorLinea]
    resultado: ResultadoDevolucion | None = None
    tipo_resolucion: TipoResolucionDevolucion | None = None
    fecha_envio: datetime | None = None
    fecha_cierre: datetime | None = None
    notas: str | None = None
    created_at: datetime = field(default_factory=_ahora)

    @staticmethod
    def crear(
        proveedor_id: UUID, recepcion_id: UUID, creado_por: UUID,
        lineas: list[DevolucionProveedorLinea], notas: str | None = None,
    ) -> "DevolucionProveedor":
        if not lineas:
            raise ValueError("Una devolución necesita al menos una línea.")
        devolucion_id = uuid4()
        for l in lineas:
            l.devolucion_id = devolucion_id
        return DevolucionProveedor(
            id=devolucion_id, proveedor_id=proveedor_id, recepcion_id=recepcion_id,
            creado_por=creado_por, estado=EstadoDevolucionProveedor.PENDIENTE,
            lineas=lineas, notas=notas,
        )

    @property
    def folio(self) -> str:
        return f"DEV-{_folio(self.id)}"

    def enviar(self) -> None:
        if self.estado != EstadoDevolucionProveedor.PENDIENTE:
            raise TransicionDevolucionInvalida(
                f"Sólo se envía una devolución 'pendiente' (está '{self.estado.value}')."
            )
        self.estado = EstadoDevolucionProveedor.ENVIADA
        self.fecha_envio = _ahora()

    def cerrar(
        self, resultado: ResultadoDevolucion, tipo_resolucion: TipoResolucionDevolucion | None = None,
    ) -> None:
        if self.estado != EstadoDevolucionProveedor.ENVIADA:
            raise TransicionDevolucionInvalida(
                f"Sólo se cierra una devolución 'enviada' (está '{self.estado.value}')."
            )
        if resultado == ResultadoDevolucion.ACEPTADA_PROVEEDOR and tipo_resolucion is None:
            raise ValueError(
                "Una devolución `aceptada_proveedor` necesita `tipo_resolucion`."
            )
        self.estado = EstadoDevolucionProveedor.CERRADA
        self.resultado = resultado
        self.tipo_resolucion = tipo_resolucion if resultado == ResultadoDevolucion.ACEPTADA_PROVEEDOR else None
        self.fecha_cierre = _ahora()
