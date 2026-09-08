from abc import ABC, abstractmethod
from dataclasses import dataclass, field
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
class PromoAplicada:
    promo_id: UUID
    etiqueta: str
    monto: Decimal


@dataclass
class LineaPromoResult:
    indice: int
    promo_id: UUID | None
    promo_etiqueta: str | None
    promo_descuento: Decimal                                  # Σ de `desglose`
    desglose: list[PromoAplicada] = field(default_factory=list)  # promos apiladas


class PromocionesPort(ABC):
    @abstractmethod
    async def evaluar(
        self, sucursal_id: UUID, lineas: list[LineaPromoInput],
        metodos_pago: frozenset[str] = frozenset(),
        cliente_segmento: str | None = None,
        codigo_cupon: str | None = None,
        telefono: str | None = None,
        cliente_id: UUID | None = None,
    ) -> list[LineaPromoResult]:
        """Descuento de promoción por línea (2x1, %, precio fijo, apilado
        combinable) para la fecha/sucursal actuales, más las condiciones de la
        venta (método de pago presente, segmento del cliente, cupón). El
        resultado viene alineado por `indice`; sin promo → `promo_descuento = 0`."""
        ...

    @abstractmethod
    async def registrar_uso_cupon(
        self, codigo: str, venta_id: UUID, monto_descontado: Decimal,
        telefono: str | None = None, cliente_id: UUID | None = None,
    ) -> None:
        """Consume el cupón para una venta ya persistida (`FOR UPDATE` + recuento).
        `CuponAgotado` si otra venta se llevó el último uso."""
        ...

    @abstractmethod
    async def liberar_cupones_de_venta(self, venta_id: UUID) -> None:
        """Anulación: borra los `cupon_uso` de la venta (libera el conteo)."""
        ...
