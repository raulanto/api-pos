from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from app.modules.inventario.domain.entities import Existencia
from app.modules.inventario.domain.exceptions import ExistenciaNoEncontrada, ProductoNoEncontrado
from app.modules.inventario.application.dtos import FiltroExistencias
from app.modules.inventario.application.ports.existencia_repository import ExistenciaRepository
from app.modules.inventario.application.ports.producto_repository import ProductoRepository
from app.shared.responses import Page, PageParams, Sort


class ConsultarExistenciasUseCase:
    """Lista existencias paginadas (con o sin filtro `solo_bajo_stock`)."""

    def __init__(self, existencia_repo: ExistenciaRepository):
        self._repo = existencia_repo

    async def ejecutar(
        self,
        filtro: FiltroExistencias,
        paginacion: PageParams,
        orden: Sort,
        includes: frozenset[str] = frozenset(),
    ) -> Page:
        return await self._repo.buscar(filtro, paginacion, orden, includes)


@dataclass
class ConfigurarUmbralesInput:
    producto_id: UUID
    sucursal_id: UUID
    stock_minimo: Decimal
    stock_maximo: Decimal | None = None


class ConfigurarUmbralesUseCase:
    def __init__(self, existencia_repo: ExistenciaRepository, producto_repo: ProductoRepository):
        self._repo = existencia_repo
        self._producto_repo = producto_repo

    async def ejecutar(self, data: ConfigurarUmbralesInput) -> Existencia:
        if data.stock_minimo < 0:
            raise ValueError("stock_minimo no puede ser negativo")
        if data.stock_maximo is not None and data.stock_maximo < data.stock_minimo:
            raise ValueError("stock_maximo no puede ser menor que stock_minimo")

        existencia = await self._repo.obtener(data.producto_id, data.sucursal_id)
        if existencia is None:
            # La existencia se crea con el primer movimiento; exigimos que exista
            # para no inventar un registro de stock 0 silenciosamente.
            producto = await self._producto_repo.obtener_por_id(data.producto_id)
            if producto is None:
                raise ProductoNoEncontrado(f"No existe el producto {data.producto_id}")
            raise ExistenciaNoEncontrada(
                "No hay registro de existencia para ese producto/sucursal; "
                "registrá primero un movimiento de entrada."
            )

        await self._repo.actualizar_umbrales(
            data.producto_id, data.sucursal_id, data.stock_minimo, data.stock_maximo
        )
        existencia.stock_minimo = data.stock_minimo
        existencia.stock_maximo = data.stock_maximo
        return existencia
