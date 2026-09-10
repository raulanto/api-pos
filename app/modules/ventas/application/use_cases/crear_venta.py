from dataclasses import dataclass
from uuid import UUID
from decimal import Decimal
from typing import List

from app.modules.ventas.domain.entities import Venta, DetalleVenta, Pago, PromoAplicada
from app.modules.ventas.domain.value_objects import EstadoVenta, MetodoPago
from app.modules.ventas.domain.exceptions import (
    CajaNoAbierta, VentaCreditoSinCliente, TurnoDeOtraSucursal, SucursalNoOperativa,
    DescuentoManualNoAutorizado, DescuentoManualExcedeTope, MotivoDescuentoRequerido,
)
from app.modules.ventas.application.ports.descuento_config_port import DescuentoConfigPort
from app.modules.sucursales.application.ports.sucursal_repository import SucursalRepository
from app.modules.ventas.application.ports.venta_repository import VentaRepository
from app.modules.ventas.application.ports.caja_repository import CajaTurnoRepository
from app.modules.ventas.application.ports.inventario_port import InventarioPort
from app.modules.ventas.application.ports.promociones_port import (
    PromocionesPort, LineaPromoInput,
)
from app.modules.ventas.application.ports.event_port import EventPort
from app.modules.ventas.application.ports.monedero_port import (
    MonederoPort, LineaAcumulacion,
)
from app.modules.clientes.application.ports.cliente_repository import ClienteRepository
from app.modules.clientes.domain.exceptions import (
    ClienteNoEncontrado, MovimientoMonederoInvalido,
)

@dataclass
class LineaInput:
    producto_id: UUID
    cantidad: Decimal
    precio_unitario: Decimal
    descuento_linea: Decimal = Decimal("0")
    impuesto_tasa: Decimal = Decimal("0")
    producto_unidad_id: UUID | None = None   # None = unidad base

@dataclass
class PagoInput:
    monto: Decimal
    metodo_pago: MetodoPago
    monto_recibido: Decimal | None = None   # sólo efectivo: con cuánto pagó el cliente

@dataclass
class CrearVentaInput:
    sucursal_id: UUID
    caja_turno_id: UUID
    usuario_id: UUID
    cliente_id: UUID | None
    descuento_total: Decimal
    lineas: List[LineaInput]
    pagos: List[PagoInput]
    idempotency_key: str | None = None
    telefono: str | None = None            # monedero: comprador; NO exige cliente
    # Descuento manual: `motivo_descuento` obligatorio si hay descuento manual;
    # `puede_descuento_manual` = el usuario tiene `ventas.descuento_manual`;
    # `rol_id` para resolver el tope de %.
    motivo_descuento: str | None = None
    puede_descuento_manual: bool = False
    rol_id: UUID | None = None
    codigo_cupon: str | None = None
    # Líneas ya construidas y con precio congelado (mayoreo/promos/unidad base ya
    # resueltos). Si viene, se usa tal cual y NO se corre `armar_lineas`. Lo usa
    # la facturación de un pedido para respetar el precio cotizado.
    lineas_congeladas: List[DetalleVenta] | None = None


@dataclass
class CotizarVentaInput:
    sucursal_id: UUID
    lineas: List[LineaInput]
    descuento_total: Decimal = Decimal("0")
    # Hints opcionales del POS para previsualizar condiciones de promo.
    metodos_pago: frozenset = frozenset()
    cliente_segmento: str | None = None
    codigo_cupon: str | None = None
    telefono: str | None = None


@dataclass
class CotizacionLinea:
    producto_id: UUID
    producto_unidad_id: UUID | None
    cantidad: Decimal
    precio_unitario: Decimal          # ya con mayoreo de unidad base si aplicó
    descuento_linea: Decimal
    impuesto_tasa: Decimal
    promo_id: UUID | None
    promo_etiqueta: str | None
    promo_descuento: Decimal
    cantidad_en_unidad_base: Decimal | None
    subtotal: Decimal
    stock_disponible: Decimal | None   # en la unidad de la línea; None = ilimitado
    hay_stock: bool


@dataclass
class CotizacionVenta:
    lineas: List[CotizacionLinea]
    descuento_total: Decimal
    total_promociones: Decimal
    total: Decimal
    monedero_a_generar: Decimal = Decimal("0")

class CrearVentaUseCase:
    def __init__(
        self,
        venta_repo: VentaRepository,
        caja_repo: CajaTurnoRepository,
        inventario: InventarioPort,
        cliente_repo: ClienteRepository,
        event_port: EventPort,
        sucursal_repo: SucursalRepository | None = None,
        promociones: PromocionesPort | None = None,
        monedero: MonederoPort | None = None,
        descuento_config: DescuentoConfigPort | None = None,
    ):
        self._venta_repo = venta_repo
        self._caja_repo = caja_repo
        self._inventario = inventario
        self._cliente_repo = cliente_repo
        self._event_port = event_port
        self._sucursal_repo = sucursal_repo
        self._promociones = promociones
        self._monedero = monedero
        self._descuento_config = descuento_config

    async def ejecutar(self, data: CrearVentaInput) -> Venta:
        # Idempotencia: si ya se procesó esta clave, devolver la venta existente.
        if data.idempotency_key:
            previa = await self._venta_repo.obtener_por_idempotency_key(data.idempotency_key)
            if previa is not None:
                return previa

        # Defensa: aunque el turno se validó al abrirlo, la sucursal pudo
        # quedar inactiva / permite_ventas=false entre medio.
        if self._sucursal_repo is not None:
            sucursal = await self._sucursal_repo.obtener_por_id(data.sucursal_id)
            if sucursal is None or not sucursal.activo or not sucursal.permite_ventas:
                raise SucursalNoOperativa(
                    f"La sucursal {data.sucursal_id} no está operativa para ventas."
                )

        turno = await self._caja_repo.obtener_por_id(data.caja_turno_id)
        if turno is None or not turno.esta_abierto:
            raise CajaNoAbierta("No hay un turno de caja abierto para esta sucursal")
        if turno.sucursal_id != data.sucursal_id:
            raise TurnoDeOtraSucursal(
                "El turno de caja indicado no pertenece a la sucursal del usuario"
            )

        metodos_pago = frozenset(p.metodo_pago.value for p in data.pagos)
        cliente_segmento = None
        if data.cliente_id is not None:
            _c = await self._cliente_repo.obtener_por_id(data.cliente_id)
            cliente_segmento = getattr(_c, "segmento", None) if _c else None

        if data.lineas_congeladas is not None:
            lineas = data.lineas_congeladas
        else:
            lineas = await self.armar_lineas(
                data.sucursal_id, data.lineas,
                metodos_pago=metodos_pago, cliente_segmento=cliente_segmento,
                codigo_cupon=data.codigo_cupon, telefono=data.telefono,
                cliente_id=data.cliente_id,
            )
        await self._validar_descuento_manual(data, lineas)
        pagos = [
            Pago.crear(monto=p.monto, metodo_pago=p.metodo_pago,
                       monto_recibido=p.monto_recibido)
            for p in data.pagos
        ]

        venta = Venta.crear(
            sucursal_id=data.sucursal_id,
            caja_turno_id=data.caja_turno_id,
            usuario_id=data.usuario_id,
            cliente_id=data.cliente_id,
            lineas=lineas,
            pagos=pagos,
            descuento_total=data.descuento_total,
            idempotency_key=data.idempotency_key,
            telefono=data.telefono,
            motivo_descuento=data.motivo_descuento,
        )

        # Pago con monedero: exige teléfono y puerto de monedero disponible.
        monedero_a_pagar = venta.monedero_usado
        if monedero_a_pagar > Decimal("0"):
            if venta.telefono is None:
                raise MovimientoMonederoInvalido(
                    "Para pagar con monedero hay que registrar el teléfono."
                )
            if self._monedero is None:
                raise MovimientoMonederoInvalido("El monedero no está disponible.")

        if venta.saldo_pendiente > Decimal("0"):
            if venta.cliente_id is None:
                raise VentaCreditoSinCliente(
                    "No se puede dejar saldo pendiente en una venta sin cliente registrado"
                )
            # FOR UPDATE: dos ventas a crédito simultáneas del mismo cliente no
            # pueden pasar las dos el chequeo de límite.
            cliente = await self._cliente_repo.obtener_por_id(
                venta.cliente_id, para_actualizar=True,
            )
            if cliente is None:
                raise ClienteNoEncontrado(f"No existe el cliente {venta.cliente_id}")
            # Única fuente de verdad de la regla de crédito: la entidad valida y
            # lanza LimiteCreditoExcedido si el saldo pendiente no cabe.
            cliente.incrementar_saldo(venta.saldo_pendiente)
            venta.estado = EstadoVenta.PENDIENTE_PAGO
            await self._cliente_repo.incrementar_saldo(venta.cliente_id, venta.saldo_pendiente)
        else:
            venta.estado = EstadoVenta.PAGADA

        await self._venta_repo.guardar(venta)

        # Mismo request => misma transacción: si una línea deja stock negativo,
        # StockInsuficiente sube y get_db() revierte TODO (venta incluida).
        for linea in venta.lineas:
            await self._inventario.descontar_stock(
                producto_id=linea.producto_id,
                sucursal_id=data.sucursal_id,
                cantidad=linea.cantidad,
                referencia_venta_id=venta.id,
                usuario_id=data.usuario_id,
                producto_unidad_id=linea.producto_unidad_id,
            )

        # Monedero (misma transacción). Consumo primero: si no alcanza el saldo,
        # SaldoMonederoInsuficiente sube y se revierte todo.
        if monedero_a_pagar > Decimal("0"):
            await self._monedero.consumir(
                venta.telefono, monedero_a_pagar, venta.id, data.usuario_id,
            )
        if venta.telefono is not None and self._monedero is not None:
            generado = await self._monedero.acumular(
                venta.telefono,
                [
                    LineaAcumulacion(
                        producto_id=l.producto_id,
                        producto_unidad_id=l.producto_unidad_id,
                        cantidad=l.cantidad, subtotal=l.subtotal,
                    )
                    for l in venta.lineas
                ],
                venta.id, data.usuario_id,
            )
            if generado > Decimal("0"):
                venta.monedero_generado = generado
                await self._venta_repo.registrar_monedero_generado(venta.id, generado)

        # Cupón: consumir el uso (FOR UPDATE + recuento). Si otro se llevó el
        # último uso, CuponAgotado sube y se revierte toda la venta.
        if data.codigo_cupon and self._promociones is not None and venta.total_promociones > 0:
            await self._promociones.registrar_uso_cupon(
                data.codigo_cupon, venta.id, venta.total_promociones,
                telefono=venta.telefono, cliente_id=venta.cliente_id,
            )

        if venta.motivo_descuento:
            desc_manual = venta.descuento_total + sum(
                (l.descuento_linea for l in venta.lineas), Decimal("0")
            )
            await self._event_port.publicar("DescuentoManualAplicado", {
                "usuario_id": data.usuario_id,
                "modulo": "ventas",
                "accion": "descuento_manual",
                "entidad": "Venta",
                "entidad_id": str(venta.id),
                "detalle": {
                    "venta_id": str(venta.id),
                    "descuento_total": str(venta.descuento_total),
                    "descuento_lineas": str(desc_manual - venta.descuento_total),
                    "monto": str(desc_manual),
                    "motivo": venta.motivo_descuento,
                    "rol_id": str(data.rol_id) if data.rol_id else None,
                },
            })

        await self._event_port.publicar("VentaCreada", {
            "usuario_id": data.usuario_id,
            "modulo": "ventas",
            "accion": "crear_venta",
            "entidad": "Venta",
            "entidad_id": str(venta.id),
            "detalle": {
                "venta_id": str(venta.id),
                "sucursal_id": str(data.sucursal_id),
                "caja_turno_id": str(data.caja_turno_id),
                "total": str(venta.total),
                "estado": venta.estado.value,
                "promociones": [
                    {"promo_id": str(a.promo_id), "etiqueta": a.etiqueta, "monto": str(a.monto)}
                    for l in venta.lineas for a in l.promos_aplicadas
                ],
            },
        })

        return venta

    # ------------------------------------------------------------------ #
    async def cotizar(self, data: CotizarVentaInput) -> CotizacionVenta:
        """Corre el MISMO pipeline de precios que `ejecutar` (mayoreo de unidad
        base + promociones + conversión a unidad base, que valida producto y
        presentación) pero NO toca stock, NO exige turno ni pagos y NO persiste.
        Para que el POS muestre el total con descuentos antes de cobrar."""
        lineas = await self.armar_lineas(
            data.sucursal_id, data.lineas,
            metodos_pago=frozenset(data.metodos_pago),
            cliente_segmento=data.cliente_segmento,
            codigo_cupon=data.codigo_cupon, telefono=data.telefono,
        )
        cot_lineas = []
        for l in lineas:
            disp = await self._inventario.stock_disponible(
                l.producto_id, data.sucursal_id, l.producto_unidad_id,
            )
            cot_lineas.append(CotizacionLinea(
                producto_id=l.producto_id,
                producto_unidad_id=l.producto_unidad_id,
                cantidad=l.cantidad,
                precio_unitario=l.precio_unitario,
                descuento_linea=l.descuento_linea,
                impuesto_tasa=l.impuesto_tasa,
                promo_id=l.promo_id,
                promo_etiqueta=l.promo_etiqueta,
                promo_descuento=l.promo_descuento,
                cantidad_en_unidad_base=l.cantidad_en_unidad_base,
                subtotal=l.subtotal,
                stock_disponible=disp,
                hay_stock=(disp is None or disp >= l.cantidad),
            ))
        total_promos = sum((l.promo_descuento for l in lineas), Decimal("0"))
        total = sum((l.subtotal for l in lineas), Decimal("0")) - data.descuento_total
        monedero = Decimal("0")
        if self._monedero is not None:
            monedero = await self._monedero.calcular_acumulacion([
                LineaAcumulacion(
                    producto_id=l.producto_id, producto_unidad_id=l.producto_unidad_id,
                    cantidad=l.cantidad, subtotal=l.subtotal,
                )
                for l in lineas
            ])
        return CotizacionVenta(
            lineas=cot_lineas,
            descuento_total=data.descuento_total,
            total_promociones=total_promos,
            total=total,
            monedero_a_generar=monedero,
        )

    # ------------------------------------------------------------------ #
    async def _validar_descuento_manual(
        self, data: CrearVentaInput, lineas: List[DetalleVenta]
    ) -> None:
        """Descuento manual (`descuento_linea`/`descuento_total`): exige permiso,
        motivo y respeta el tope de % del rol. Sólo se aplica si el use case
        recibió `descuento_config` (en tests legacy queda desactivado)."""
        if self._descuento_config is None:
            return
        hay_manual = data.descuento_total > 0 or any(l.descuento_linea > 0 for l in lineas)
        if not hay_manual:
            return
        if not data.puede_descuento_manual:
            raise DescuentoManualNoAutorizado(
                "Se requiere el permiso `ventas.descuento_manual` para aplicar un "
                "descuento manual."
            )
        if not (data.motivo_descuento and data.motivo_descuento.strip()):
            raise MotivoDescuentoRequerido(
                "El descuento manual requiere `motivo_descuento`."
            )
        pct_max = (
            await self._descuento_config.pct_max_para_rol(data.rol_id)
            if data.rol_id is not None else None
        )
        if pct_max is None:
            return
        for l in lineas:
            bruto = l.cantidad * l.precio_unitario
            if l.descuento_linea > 0 and bruto > 0 and (l.descuento_linea / bruto * 100) > pct_max:
                raise DescuentoManualExcedeTope(
                    f"El descuento de línea supera el tope de {pct_max}% del rol."
                )
        total_bruto = sum((l.cantidad * l.precio_unitario for l in lineas), Decimal("0"))
        if (
            data.descuento_total > 0 and total_bruto > 0
            and (data.descuento_total / total_bruto * 100) > pct_max
        ):
            raise DescuentoManualExcedeTope(
                f"El descuento total supera el tope de {pct_max}% del rol."
            )

    # ------------------------------------------------------------------ #
    async def armar_lineas(
        self, sucursal_id: UUID, lineas_input: List[LineaInput],
        *, metodos_pago: frozenset = frozenset(), cliente_segmento: str | None = None,
        codigo_cupon: str | None = None, telefono: str | None = None,
        cliente_id: UUID | None = None,
    ) -> List[DetalleVenta]:
        """Construye las líneas con el precio final: mayoreo de unidad base,
        descuento de promoción congelado, y `cantidad_en_unidad_base`."""
        lineas = []
        for l in lineas_input:
            precio = l.precio_unitario
            # Mayoreo: sólo en venta por unidad base; el backend fuerza el precio
            # y lo congela en detalle_venta (ignora el que mandó el front).
            if l.producto_unidad_id is None:
                mayoreo = await self._inventario.precio_mayoreo_aplicable(
                    l.producto_id, l.cantidad
                )
                if mayoreo is not None:
                    precio = mayoreo
            lineas.append(DetalleVenta.crear(
                producto_id=l.producto_id,
                cantidad=l.cantidad,
                precio_unitario=precio,
                descuento_linea=l.descuento_linea,
                impuesto_tasa=l.impuesto_tasa,
                producto_unidad_id=l.producto_unidad_id,
            ))

        # Promociones (2x1, %, precio fijo por presentación): se evalúan sobre el
        # precio ya con mayoreo y se congelan en la línea. El motor es defensivo:
        # una promo mal configurada simplemente no aplica.
        if self._promociones is not None:
            evaluacion = await self._promociones.evaluar(
                sucursal_id,
                [
                    LineaPromoInput(
                        indice=i, producto_id=linea.producto_id,
                        producto_unidad_id=linea.producto_unidad_id,
                        cantidad=linea.cantidad, precio_unitario=linea.precio_unitario,
                    )
                    for i, linea in enumerate(lineas)
                ],
                metodos_pago=metodos_pago, cliente_segmento=cliente_segmento,
                codigo_cupon=codigo_cupon, telefono=telefono, cliente_id=cliente_id,
            )
            for res in evaluacion:
                if res.promo_descuento > 0:
                    linea = lineas[res.indice]
                    linea.promo_id = res.promo_id
                    linea.promo_etiqueta = res.promo_etiqueta
                    linea.promo_descuento = res.promo_descuento
                    linea.promos_aplicadas = [
                        PromoAplicada(promo_id=a.promo_id, etiqueta=a.etiqueta, monto=a.monto)
                        for a in (res.desglose or [])
                    ]

        # Cantidad en unidad base (cantidad * factor); valida producto/presentación.
        # Se persiste para no recalcularla en anulaciones ni reportes.
        for linea in lineas:
            linea.cantidad_en_unidad_base = await self._inventario.convertir_a_base(
                producto_id=linea.producto_id,
                cantidad=linea.cantidad,
                producto_unidad_id=linea.producto_unidad_id,
            )
        return lineas
