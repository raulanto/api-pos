from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ventas.application.ports.promociones_port import (
    PromocionesPort, LineaPromoInput, LineaPromoResult,
)
from app.modules.promociones.application.use_cases.evaluar_promociones import (
    EvaluarPromocionesUseCase,
)
from app.modules.promociones.domain.services import LineaEval
from app.modules.promociones.infrastructure.persistence.promocion_repository_impl import (
    SqlAlchemyPromocionRepository,
)


class PromocionesPortImpl(PromocionesPort):
    """Adaptador: arma el caso de uso de `promociones` con la MISMA sesión del
    request (todo cae en la transacción única de `get_db`)."""

    def __init__(self, db: AsyncSession):
        self._use_case = EvaluarPromocionesUseCase(SqlAlchemyPromocionRepository(db))

    async def evaluar(
        self, sucursal_id: UUID, lineas: list[LineaPromoInput],
    ) -> list[LineaPromoResult]:
        entrada = [
            LineaEval(
                indice=l.indice, producto_id=l.producto_id,
                producto_unidad_id=l.producto_unidad_id,
                cantidad=l.cantidad, precio_unitario=l.precio_unitario,
            )
            for l in lineas
        ]
        resultados = await self._use_case.ejecutar(sucursal_id, entrada)
        return [
            LineaPromoResult(
                indice=r.indice, promo_id=r.promo_id,
                promo_etiqueta=r.promo_etiqueta, promo_descuento=r.promo_descuento,
            )
            for r in resultados
        ]
