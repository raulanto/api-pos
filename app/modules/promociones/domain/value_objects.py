from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from uuid import UUID


@dataclass
class ContextoEvaluacion:
    """Todo lo que el motor necesita saber de la venta, más allá de las líneas.
    Se pasa entero a `evaluar()` para no re-threadear firmas fase a fase."""
    momento: datetime
    sucursal_id: UUID
    total_bruto: Decimal = Decimal("0")               # Σ cantidad*precio (monto_minimo_compra)
    metodos_pago: frozenset[str] = field(default_factory=frozenset)
    cliente_segmento: str | None = None
    promos_por_cupon: frozenset[UUID] = field(default_factory=frozenset)
