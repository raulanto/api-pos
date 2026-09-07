from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID


@dataclass
class LineaPromoInput:
    indice: int
    producto_id: UUID
    producto_unidad_id: UUID | None
    cantidad: Decimal
    precio_unitario: Decimal   # ya con el mayoreo de unidad base si aplicó


@dataclass
class LineaPromoResult:
    indice: int
    promo_id: UUID | None
    promo_etiqueta: str | None
    promo_descuento: Decimal


class PromocionesPort(ABC):
    @abstractmethod
    async def evaluar(
        self, sucursal_id: UUID, lineas: list[LineaPromoInput],
    ) -> list[LineaPromoResult]:
        """Descuento de promoción por línea (2x1, %, precio fijo/mayoreo por
        presentación) evaluado a la fecha actual y la sucursal. El resultado
        viene alineado por `indice`; una línea sin promo trae `promo_descuento = 0`."""
        ...
