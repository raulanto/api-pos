from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ventas.application.ports.promociones_port import (
    PromocionesPort, LineaPromoInput, LineaPromoResult, PromoAplicada,
)
from app.modules.promociones.application.use_cases.evaluar_promociones import (
    EvaluarPromocionesUseCase,
)
from decimal import Decimal

from app.modules.promociones.application.use_cases.validar_cupon import (
    ValidarCuponUseCase, ConsumirCuponUseCase,
)
from app.modules.promociones.domain.services import LineaEval
from app.modules.promociones.infrastructure.persistence.promocion_repository_impl import (
    SqlAlchemyPromocionRepository,
)
from app.modules.promociones.infrastructure.persistence.cupon_repository_impl import (
    SqlAlchemyCuponRepository,
)
from app.modules.inventario.infrastructure.persistence.repositories.producto import (
    SqlAlchemyProductoRepository,
)


class PromocionesPortImpl(PromocionesPort):
    """Adaptador: arma el caso de uso de `promociones` con la MISMA sesión del
    request (todo cae en la transacción única de `get_db`)."""

    def __init__(self, db: AsyncSession):
        self._use_case = EvaluarPromocionesUseCase(SqlAlchemyPromocionRepository(db))
        self._producto_repo = SqlAlchemyProductoRepository(db)
        self._cupon_repo = SqlAlchemyCuponRepository(db)
        self._cache_categoria: dict[UUID, UUID | None] = {}

    async def _categoria(self, producto_id: UUID) -> UUID | None:
        if producto_id not in self._cache_categoria:
            p = await self._producto_repo.obtener_por_id(producto_id)
            self._cache_categoria[producto_id] = p.categoria_id if p else None
        return self._cache_categoria[producto_id]

    async def evaluar(
        self, sucursal_id: UUID, lineas: list[LineaPromoInput],
        metodos_pago: frozenset[str] = frozenset(),
        cliente_segmento: str | None = None,
        codigo_cupon: str | None = None,
        telefono: str | None = None,
        cliente_id: UUID | None = None,
    ) -> list[LineaPromoResult]:
        entrada = [
            LineaEval(
                indice=l.indice, producto_id=l.producto_id,
                producto_unidad_id=l.producto_unidad_id,
                cantidad=l.cantidad, precio_unitario=l.precio_unitario,
                categoria_id=await self._categoria(l.producto_id),
            )
            for l in lineas
        ]

        promos_por_cupon: frozenset[UUID] = frozenset()
        if codigo_cupon:
            pid = await ValidarCuponUseCase(self._cupon_repo).ejecutar(
                codigo_cupon, telefono=telefono, cliente_id=cliente_id,
            )
            promos_por_cupon = frozenset({pid})

        resultados = await self._use_case.ejecutar(
            sucursal_id, entrada,
            metodos_pago=metodos_pago, cliente_segmento=cliente_segmento,
            promos_por_cupon=promos_por_cupon,
        )
        return [
            LineaPromoResult(
                indice=r.indice, promo_id=r.promo_id,
                promo_etiqueta=r.promo_etiqueta, promo_descuento=r.promo_descuento,
                desglose=[
                    PromoAplicada(promo_id=a.promo_id, etiqueta=a.etiqueta, monto=a.monto)
                    for a in r.desglose
                ],
            )
            for r in resultados
        ]

    async def registrar_uso_cupon(
        self, codigo: str, venta_id: UUID, monto_descontado: Decimal,
        telefono: str | None = None, cliente_id: UUID | None = None,
    ) -> None:
        await ConsumirCuponUseCase(self._cupon_repo).ejecutar(
            codigo, venta_id, monto_descontado, telefono=telefono, cliente_id=cliente_id,
        )

    async def liberar_cupones_de_venta(self, venta_id: UUID) -> None:
        await self._cupon_repo.borrar_usos_de_venta(venta_id)
