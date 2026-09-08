from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID


@dataclass
class LineaAcumulacion:
    """Datos primitivos de una línea de venta para calcular el cashback."""
    producto_id: UUID
    producto_unidad_id: UUID | None
    cantidad: Decimal
    subtotal: Decimal


class MonederoPort(ABC):
    """Puerto de ventas hacia el monedero (módulo `clientes`). Tipos primitivos:
    ventas no conoce las entidades del monedero."""

    @abstractmethod
    async def calcular_acumulacion(self, lineas: list[LineaAcumulacion]) -> Decimal:
        """Sin persistir: cuánto monedero generarían estas líneas (para `cotizar`)."""
        ...

    @abstractmethod
    async def acumular(
        self, telefono: str, lineas: list[LineaAcumulacion],
        venta_id: UUID, usuario_id: UUID,
    ) -> Decimal:
        """Acredita el cashback al teléfono (crea la cuenta si no existe).
        Devuelve el total acreditado (0 si nada aplica)."""
        ...

    @abstractmethod
    async def consumir(
        self, telefono: str, monto: Decimal, venta_id: UUID, usuario_id: UUID,
    ) -> None:
        """Debita `monto` del monedero. `SaldoMonederoInsuficiente` si no alcanza
        o el teléfono no tiene cuenta."""
        ...

    @abstractmethod
    async def reintegrar(
        self, telefono: str, monto: Decimal, venta_id: UUID, usuario_id: UUID,
        motivo: str,
    ) -> None:
        """Devuelve `monto` al monedero (devolución con metodo=monedero)."""
        ...

    @abstractmethod
    async def revertir_venta(
        self, telefono: str | None, venta_id: UUID, usuario_id: UUID,
    ) -> None:
        """Anulación: revierte los movimientos de monedero de la venta —
        acumulaciones (con tope en el saldo actual) y consumos."""
        ...
