from datetime import datetime, timezone
from uuid import UUID

from app.modules.promociones.application.ports.promocion_repository import PromocionRepository
from app.modules.promociones.domain.services import LineaEval, ResultadoLinea, evaluar


class EvaluarPromocionesUseCase:
    def __init__(self, repo: PromocionRepository):
        self._repo = repo

    async def ejecutar(
        self, sucursal_id: UUID, lineas: list[LineaEval],
        momento: datetime | None = None,
    ) -> list[ResultadoLinea]:
        if not lineas:
            return []
        momento = momento or datetime.now(timezone.utc)
        promos = await self._repo.listar_vigentes(momento, sucursal_id)
        return evaluar(promos, lineas, momento, sucursal_id)
