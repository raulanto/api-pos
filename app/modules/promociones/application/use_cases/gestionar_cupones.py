from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.modules.promociones.application.ports.cupon_repository import CuponRepository
from app.modules.promociones.application.ports.promocion_repository import PromocionRepository
from app.modules.promociones.domain.entities import Cupon
from app.modules.promociones.domain.exceptions import (
    PromocionNoEncontrada, PromocionInvalida, CuponNoEncontrado,
)


@dataclass
class CrearCuponInput:
    promocion_id: UUID
    codigo: str
    vigente_desde: datetime | None = None
    vigente_hasta: datetime | None = None
    max_usos_total: int | None = None
    max_usos_por_persona: int | None = None


class CrearCuponUseCase:
    def __init__(self, cupon_repo: CuponRepository, promo_repo: PromocionRepository):
        self._repo = cupon_repo
        self._promo_repo = promo_repo

    async def ejecutar(self, data: CrearCuponInput) -> Cupon:
        promo = await self._promo_repo.obtener_por_id(data.promocion_id)
        if promo is None:
            raise PromocionNoEncontrada(f"No existe la promoción {data.promocion_id}")
        if await self._repo.obtener_por_codigo(data.codigo) is not None:
            raise PromocionInvalida(f"Ya existe un cupón con el código '{data.codigo}'.")
        cupon = Cupon.crear(
            codigo=data.codigo, promocion_id=data.promocion_id,
            vigente_desde=data.vigente_desde, vigente_hasta=data.vigente_hasta,
            max_usos_total=data.max_usos_total,
            max_usos_por_persona=data.max_usos_por_persona,
        )
        await self._repo.crear(cupon)
        return cupon


class ListarCuponesUseCase:
    def __init__(self, cupon_repo: CuponRepository):
        self._repo = cupon_repo

    async def ejecutar(self, promocion_id: UUID) -> list[Cupon]:
        return await self._repo.listar_por_promocion(promocion_id)


class DesactivarCuponUseCase:
    def __init__(self, cupon_repo: CuponRepository):
        self._repo = cupon_repo

    async def ejecutar(self, codigo: str) -> Cupon:
        cupon = await self._repo.obtener_por_codigo(codigo)
        if cupon is None:
            raise CuponNoEncontrado(f"No hay un cupón con el código '{codigo}'.")
        cupon.activo = False
        await self._repo.actualizar(cupon)
        return cupon
