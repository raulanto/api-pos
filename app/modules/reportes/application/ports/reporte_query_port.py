from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

NOTA_ARQUEO = "Solo el efectivo se considera para el arqueo físico de caja."


# --------------------------------------------------------------------------- #
# Corte de caja
# --------------------------------------------------------------------------- #
@dataclass
class CorteDeCajaOutput:
    caja_turno_id: UUID
    monto_inicial: Decimal
    total_efectivo: Decimal
    total_tarjeta: Decimal
    total_transferencia: Decimal
    total_credito: Decimal
    monto_final_esperado: Decimal  # = monto_inicial + total_efectivo
    nota: str = NOTA_ARQUEO


# --------------------------------------------------------------------------- #
# Reporte de ventas por rango
# --------------------------------------------------------------------------- #
@dataclass
class VentasDiaOutput:
    dia: date
    numero_ventas: int
    total: Decimal


@dataclass
class ReporteVentasOutput:
    desde: datetime
    hasta: datetime
    sucursal_id: UUID | None
    total_vendido: Decimal
    numero_ventas: int
    ticket_promedio: Decimal
    por_dia: list[VentasDiaOutput] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# Ventas por método de pago
# --------------------------------------------------------------------------- #
@dataclass
class MetodoPagoTotalOutput:
    metodo_pago: str
    total: Decimal


@dataclass
class VentasPorMetodoOutput:
    desde: datetime
    hasta: datetime
    sucursal_id: UUID | None
    total_efectivo: Decimal
    total_tarjeta: Decimal
    total_transferencia: Decimal
    total_credito: Decimal
    total_general: Decimal
    detalle: list[MetodoPagoTotalOutput] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# Ventas por usuario / producto
# --------------------------------------------------------------------------- #
@dataclass
class VentaPorUsuarioOutput:
    usuario_id: UUID
    nombre: str
    numero_ventas: int
    total_vendido: Decimal


@dataclass
class ProductoRankingOutput:
    producto_id: UUID
    sku: str
    nombre: str
    cantidad_vendida: Decimal
    monto_total: Decimal


# --------------------------------------------------------------------------- #
# Inventario valorizado
# --------------------------------------------------------------------------- #
@dataclass
class CategoriaValorizadaOutput:
    categoria_id: UUID
    nombre: str
    valor: Decimal
    numero_productos: int


@dataclass
class InventarioValorizadoOutput:
    sucursal_id: UUID | None
    categoria_id: UUID | None
    valor_total: Decimal
    por_categoria: list[CategoriaValorizadaOutput] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# Cartera de crédito
# --------------------------------------------------------------------------- #
@dataclass
class ClienteSaldoOutput:
    cliente_id: UUID
    nombre: str
    saldo_credito: Decimal
    limite_credito: Decimal


@dataclass
class PaginaReporte:
    items: list
    total: int


# --------------------------------------------------------------------------- #
class ReporteQueryPort(ABC):
    @abstractmethod
    async def calcular_corte_caja(self, caja_turno_id: UUID) -> CorteDeCajaOutput: ...

    @abstractmethod
    async def reporte_ventas(
        self, desde: datetime, hasta: datetime, sucursal_id: UUID | None = None
    ) -> ReporteVentasOutput: ...

    @abstractmethod
    async def ventas_por_metodo_pago(
        self, desde: datetime, hasta: datetime, sucursal_id: UUID | None = None
    ) -> VentasPorMetodoOutput: ...

    @abstractmethod
    async def ventas_por_usuario(
        self, desde: datetime, hasta: datetime, sucursal_id: UUID | None = None,
        limit: int = 50, offset: int = 0,
    ) -> PaginaReporte: ...

    @abstractmethod
    async def top_productos(
        self, desde: datetime, hasta: datetime, sucursal_id: UUID | None = None,
        limit: int = 20, offset: int = 0,
    ) -> PaginaReporte: ...

    @abstractmethod
    async def inventario_valorizado(
        self, sucursal_id: UUID | None = None, categoria_id: UUID | None = None
    ) -> InventarioValorizadoOutput: ...

    @abstractmethod
    async def clientes_con_saldo(
        self, sucursal_id: UUID | None = None, limit: int = 50, offset: int = 0
    ) -> PaginaReporte: ...
