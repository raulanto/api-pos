from uuid import UUID

from app.modules.ventas.domain.entities import Venta
from app.modules.ventas.domain.exceptions import VentaNoEncontrada
from app.modules.ventas.application.dtos import FiltroVentas
from app.modules.ventas.application.ports.venta_repository import VentaRepository
from app.shared.responses import Page, PageParams, Sort


class ListarVentasUseCase:
    def __init__(self, venta_repo: VentaRepository):
        self._repo = venta_repo

    async def ejecutar(
        self, filtro: FiltroVentas, paginacion: PageParams, orden: Sort
    ) -> Page:
        return await self._repo.listar(filtro, paginacion, orden)


class ObtenerVentaUseCase:
    def __init__(self, venta_repo: VentaRepository):
        self._repo = venta_repo

    async def ejecutar(self, venta_id: UUID) -> Venta:
        venta = await self._repo.obtener_por_id(venta_id)
        if venta is None:
            raise VentaNoEncontrada(f"No existe la venta {venta_id}")
        return venta
