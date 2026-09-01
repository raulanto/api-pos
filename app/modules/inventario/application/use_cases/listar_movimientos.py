from uuid import UUID

from app.modules.inventario.domain.entities import MovimientoInventario
from app.modules.inventario.domain.exceptions import MovimientoNoEncontrado
from app.modules.inventario.application.dtos import FiltroMovimientos
from app.shared.responses import Page, PageParams, Sort
from app.modules.inventario.application.ports.movimiento_repository import MovimientoRepository


class ListarMovimientosUseCase:
    def __init__(self, movimiento_repo: MovimientoRepository):
        self._repo = movimiento_repo

    async def ejecutar(
        self,
        filtro: FiltroMovimientos,
        paginacion: PageParams,
        orden: Sort,
        includes: frozenset[str] = frozenset(),
    ) -> Page:
        return await self._repo.listar(filtro, paginacion, orden, includes)


class ObtenerMovimientoUseCase:
    def __init__(self, movimiento_repo: MovimientoRepository):
        self._repo = movimiento_repo

    async def ejecutar(
        self, movimiento_id: UUID, includes: frozenset[str] = frozenset()
    ) -> MovimientoInventario:
        movimiento = await self._repo.obtener_por_id(movimiento_id, includes)
        if not movimiento:
            raise MovimientoNoEncontrado(f"No existe el movimiento {movimiento_id}")
        return movimiento
