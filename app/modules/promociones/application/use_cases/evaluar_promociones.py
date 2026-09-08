from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from app.modules.promociones.application.ports.promocion_repository import PromocionRepository
from app.modules.promociones.domain.services import LineaEval, ResultadoLinea, evaluar
from app.modules.promociones.domain.value_objects import ContextoEvaluacion


class EvaluarPromocionesUseCase:
    def __init__(self, repo: PromocionRepository):
        self._repo = repo

    async def ejecutar(
        self, sucursal_id: UUID, lineas: list[LineaEval],
        momento: datetime | None = None,
        metodos_pago: frozenset[str] = frozenset(),
        cliente_segmento: str | None = None,
        promos_por_cupon: frozenset[UUID] = frozenset(),
    ) -> list[ResultadoLinea]:
        if not lineas:
            return []
        momento = momento or datetime.now(timezone.utc)
        total_bruto = sum(
            (l.cantidad * l.precio_unitario for l in lineas), Decimal("0")
        )
        ctx = ContextoEvaluacion(
            momento=momento, sucursal_id=sucursal_id, total_bruto=total_bruto,
            metodos_pago=metodos_pago, cliente_segmento=cliente_segmento,
            promos_por_cupon=promos_por_cupon,
        )
        promos = await self._repo.listar_vigentes(momento, sucursal_id)
        return evaluar(promos, lineas, ctx)
