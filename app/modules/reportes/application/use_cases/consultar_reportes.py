"""Casos de uso de reportes: son delegaciones finas al ReporteQueryPort
(un módulo de solo lectura no tiene lógica de dominio propia)."""
from datetime import datetime
from uuid import UUID

from app.modules.reportes.application.ports.reporte_query_port import (
    ReporteQueryPort, ReporteVentasOutput, VentasPorMetodoOutput,
    InventarioValorizadoOutput, PaginaReporte,
)


class ReporteVentasUseCase:
    def __init__(self, query_port: ReporteQueryPort):
        self._q = query_port

    async def ejecutar(
        self, desde: datetime, hasta: datetime, sucursal_id: UUID | None = None
    ) -> ReporteVentasOutput:
        return await self._q.reporte_ventas(desde, hasta, sucursal_id)


class VentasPorMetodoPagoUseCase:
    def __init__(self, query_port: ReporteQueryPort):
        self._q = query_port

    async def ejecutar(
        self, desde: datetime, hasta: datetime, sucursal_id: UUID | None = None
    ) -> VentasPorMetodoOutput:
        return await self._q.ventas_por_metodo_pago(desde, hasta, sucursal_id)


class VentasPorUsuarioUseCase:
    def __init__(self, query_port: ReporteQueryPort):
        self._q = query_port

    async def ejecutar(
        self, desde: datetime, hasta: datetime, sucursal_id: UUID | None = None,
        limit: int = 50, offset: int = 0,
    ) -> PaginaReporte:
        return await self._q.ventas_por_usuario(desde, hasta, sucursal_id, limit, offset)


class ProductosMasVendidosUseCase:
    def __init__(self, query_port: ReporteQueryPort):
        self._q = query_port

    async def ejecutar(
        self, desde: datetime, hasta: datetime, sucursal_id: UUID | None = None,
        limit: int = 20, offset: int = 0,
    ) -> PaginaReporte:
        return await self._q.top_productos(desde, hasta, sucursal_id, limit, offset)


class InventarioValorizadoUseCase:
    def __init__(self, query_port: ReporteQueryPort):
        self._q = query_port

    async def ejecutar(
        self, sucursal_id: UUID | None = None, categoria_id: UUID | None = None
    ) -> InventarioValorizadoOutput:
        return await self._q.inventario_valorizado(sucursal_id, categoria_id)


class ClientesConSaldoUseCase:
    def __init__(self, query_port: ReporteQueryPort):
        self._q = query_port

    async def ejecutar(
        self, sucursal_id: UUID | None = None, limit: int = 50, offset: int = 0
    ) -> PaginaReporte:
        return await self._q.clientes_con_saldo(sucursal_id, limit, offset)
