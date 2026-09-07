"""Arma los datos del ticket de una venta (sin PDF: sólo texto + números)."""
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from app.modules.ventas.domain.exceptions import VentaNoEncontrada
from app.modules.ventas.application.ports.venta_repository import VentaRepository
from app.modules.inventario.application.ports.producto_repository import ProductoRepository
from app.modules.sucursales.application.ports.sucursal_repository import SucursalRepository


@dataclass
class TicketLinea:
    nombre: str
    cantidad: Decimal
    precio_unitario: Decimal
    descuento: Decimal      # descuento_linea + promo_descuento
    promo_etiqueta: str | None
    importe: Decimal        # subtotal ya neto


@dataclass
class TicketPago:
    metodo: str
    monto: Decimal
    monto_recibido: Decimal | None
    cambio: Decimal


@dataclass
class TicketData:
    venta_id: UUID
    sucursal_id: UUID
    folio: str                      # id corto de la venta
    fecha: datetime
    estado: str
    sucursal_nombre: str
    sucursal_direccion: str | None
    sucursal_telefono: str | None
    cliente_nombre: str | None
    lineas: list[TicketLinea]
    subtotal: Decimal               # Σ importes de línea
    descuento_total: Decimal
    total_promociones: Decimal
    total: Decimal
    total_devuelto: Decimal
    pagos: list[TicketPago] = field(default_factory=list)
    total_pagado: Decimal = Decimal("0")
    cambio: Decimal = Decimal("0")
    saldo_pendiente: Decimal = Decimal("0")


class GenerarTicketUseCase:
    def __init__(
        self,
        venta_repo: VentaRepository,
        producto_repo: ProductoRepository,
        sucursal_repo: SucursalRepository,
    ):
        self._venta_repo = venta_repo
        self._producto_repo = producto_repo
        self._sucursal_repo = sucursal_repo

    async def ejecutar(self, venta_id: UUID) -> TicketData:
        venta = await self._venta_repo.obtener_por_id(venta_id, frozenset({"cliente"}))
        if venta is None:
            raise VentaNoEncontrada(f"No existe la venta {venta_id}")

        sucursal = await self._sucursal_repo.obtener_por_id(venta.sucursal_id)
        nombres: dict[UUID, str] = {}
        for linea in venta.lineas:
            if linea.producto_id not in nombres:
                p = await self._producto_repo.obtener_por_id(linea.producto_id)
                nombres[linea.producto_id] = p.nombre if p is not None else str(linea.producto_id)

        lineas = [
            TicketLinea(
                nombre=nombres[l.producto_id],
                cantidad=l.cantidad,
                precio_unitario=l.precio_unitario,
                descuento=l.descuento_linea + l.promo_descuento,
                promo_etiqueta=l.promo_etiqueta,
                importe=l.subtotal,
            )
            for l in venta.lineas
        ]
        cliente_nombre = getattr(venta.cliente, "nombre", None) if venta.cliente else None

        return TicketData(
            venta_id=venta.id,
            sucursal_id=venta.sucursal_id,
            folio=str(venta.id)[:8],
            fecha=venta.created_at,
            estado=venta.estado.value,
            sucursal_nombre=sucursal.nombre if sucursal else str(venta.sucursal_id),
            sucursal_direccion=getattr(sucursal, "direccion", None),
            sucursal_telefono=getattr(sucursal, "telefono", None),
            cliente_nombre=cliente_nombre,
            lineas=lineas,
            subtotal=sum((l.importe for l in lineas), Decimal("0")),
            descuento_total=venta.descuento_total,
            total_promociones=venta.total_promociones,
            total=venta.total,
            total_devuelto=venta.total_devuelto,
            pagos=[
                TicketPago(
                    metodo=p.metodo_pago.value, monto=p.monto,
                    monto_recibido=p.monto_recibido, cambio=p.cambio,
                )
                for p in venta.pagos
            ],
            total_pagado=venta.monto_pagado,
            cambio=venta.cambio,
            saldo_pendiente=venta.saldo_pendiente,
        )
