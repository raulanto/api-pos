from dataclasses import dataclass
from uuid import UUID

from app.modules.inventario.domain.entities import Marca
from app.modules.inventario.domain.exceptions import (
    MarcaNoEncontrada, MarcaConProductosActivos,
)
from app.modules.inventario.application.dtos import FiltroMarcas
from app.modules.inventario.application.ports.marca_repository import MarcaRepository
from app.shared.responses import Page, PageParams, Sort


@dataclass
class CrearMarcaInput:
    nombre: str


class CrearMarcaUseCase:
    def __init__(self, marca_repo: MarcaRepository):
        self._repo = marca_repo

    async def ejecutar(self, data: CrearMarcaInput) -> Marca:
        marca = Marca.crear(nombre=data.nombre)
        await self._repo.guardar(marca)
        return marca


class ListarMarcasUseCase:
    def __init__(self, marca_repo: MarcaRepository):
        self._repo = marca_repo

    async def ejecutar(
        self,
        filtro: FiltroMarcas,
        paginacion: PageParams,
        orden: Sort,
    ) -> Page:
        return await self._repo.listar(filtro, paginacion, orden)


class ObtenerMarcaUseCase:
    def __init__(self, marca_repo: MarcaRepository):
        self._repo = marca_repo

    async def ejecutar(self, marca_id: UUID) -> Marca:
        marca = await self._repo.obtener_por_id(marca_id)
        if not marca:
            raise MarcaNoEncontrada(f"No existe la marca {marca_id}")
        return marca


@dataclass
class ActualizarMarcaInput:
    marca_id: UUID
    nombre: str | None = None


class ActualizarMarcaUseCase:
    def __init__(self, marca_repo: MarcaRepository):
        self._repo = marca_repo

    async def ejecutar(self, data: ActualizarMarcaInput) -> Marca:
        marca = await self._repo.obtener_por_id(data.marca_id)
        if not marca:
            raise MarcaNoEncontrada(f"No existe la marca {data.marca_id}")

        marca.actualizar(nombre=data.nombre)
        await self._repo.actualizar(marca)
        return marca


class DesactivarMarcaUseCase:
    def __init__(self, marca_repo: MarcaRepository):
        self._repo = marca_repo

    async def ejecutar(self, marca_id: UUID) -> Marca:
        marca = await self._repo.obtener_por_id(marca_id)
        if not marca:
            raise MarcaNoEncontrada(f"No existe la marca {marca_id}")
        if await self._repo.tiene_productos_activos(marca_id):
            raise MarcaConProductosActivos(
                "No se puede desactivar una marca con productos activos asociados; "
                "reasigná o desactivá esos productos primero."
            )
        marca.desactivar()
        await self._repo.actualizar(marca)
        return marca


class ReactivarMarcaUseCase:
    def __init__(self, marca_repo: MarcaRepository):
        self._repo = marca_repo

    async def ejecutar(self, marca_id: UUID) -> Marca:
        marca = await self._repo.obtener_por_id(marca_id)
        if not marca:
            raise MarcaNoEncontrada(f"No existe la marca {marca_id}")
        marca.activar()
        await self._repo.actualizar(marca)
        return marca


class EliminarMarcaUseCase:
    def __init__(self, marca_repo: MarcaRepository):
        self._repo = marca_repo

    async def ejecutar(self, marca_id: UUID) -> None:
        marca = await self._repo.obtener_por_id(marca_id)
        if not marca:
            raise MarcaNoEncontrada(f"No existe la marca {marca_id}")
        if await self._repo.tiene_productos_activos(marca_id):
            raise MarcaConProductosActivos(
                "No se puede eliminar una marca con productos activos asociados; "
                "reasigná o desactivá esos productos primero."
            )
        await self._repo.eliminar(marca_id)

