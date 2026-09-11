from dataclasses import dataclass, field
from decimal import Decimal
from typing import List
from uuid import UUID

from app.modules.agenda.application.ports.cita_repository import CitaRepository
from app.modules.agenda.domain.value_objects import EstadoCita
from app.modules.agenda.domain.exceptions import CitaNoEncontrada, CitaNoFacturable, CitaYaFacturada
from app.modules.inventario.application.ports.producto_repository import ProductoRepository
from app.modules.ventas.application.use_cases.crear_venta import (
    CrearVentaUseCase, CrearVentaInput, PagoInput,
)
from app.modules.ventas.domain.entities import Venta, DetalleVenta


@dataclass
class FacturarCitaInput:
    cita_id: UUID
    usuario_id: UUID
    caja_turno_id: UUID
    pagos: List[PagoInput] = field(default_factory=list)
    idempotency_key: str | None = None


class FacturarCitaUseCase:
    """Convierte una cita `completada` en una `Venta` real reusando
    `CrearVentaUseCase` (stock no aplica: el servicio no mueve inventario, pero
    sí caja/monedero/cupón/crédito). La línea llega con precio congelado (el del
    `producto` servicio al momento de facturar) y `cita_id` para trazabilidad.
    Mismo patrón que `pedidos.FacturarPedidoUseCase` (ventas no conoce `agenda`,
    es `agenda` quien reusa el caso de uso de ventas)."""

    def __init__(
        self, cita_repo: CitaRepository, producto_repo: ProductoRepository,
        crear_venta_uc: CrearVentaUseCase,
    ):
        self._cita_repo = cita_repo
        self._producto_repo = producto_repo
        self._venta_uc = crear_venta_uc

    async def ejecutar(self, data: FacturarCitaInput) -> Venta:
        cita = await self._cita_repo.obtener_por_id(data.cita_id, para_actualizar=True)
        if cita is None:
            raise CitaNoEncontrada(f"No existe la cita {data.cita_id}")
        if cita.venta_detalle_id is not None:
            raise CitaYaFacturada(f"La cita {cita.id} ya fue facturada.")
        if cita.estado != EstadoCita.COMPLETADA:
            raise CitaNoFacturable(
                f"Sólo se factura una cita 'completada' (está '{cita.estado.value}')."
            )

        producto = await self._producto_repo.obtener_por_id(cita.servicio_id)
        detalle = DetalleVenta.crear(
            producto_id=cita.servicio_id, cantidad=Decimal("1"),
            precio_unitario=producto.precio_venta if producto else Decimal("0"),
            impuesto_tasa=producto.impuesto_tasa if producto else Decimal("0"),
            cita_id=cita.id,
        )

        venta = await self._venta_uc.ejecutar(CrearVentaInput(
            sucursal_id=cita.sucursal_id, caja_turno_id=data.caja_turno_id,
            usuario_id=data.usuario_id, cliente_id=cita.cliente_id,
            descuento_total=Decimal("0"), lineas=[], pagos=data.pagos,
            idempotency_key=data.idempotency_key,
            lineas_congeladas=[detalle], puede_descuento_manual=True,
        ))

        cita.vincular_venta(detalle.id)
        await self._cita_repo.actualizar(cita)
        return venta
