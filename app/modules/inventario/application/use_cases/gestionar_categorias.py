from dataclasses import dataclass
from uuid import UUID

from app.modules.inventario.domain.entities import Categoria
from app.modules.inventario.domain.exceptions import (
    CategoriaNoEncontrada, JerarquiaCategoriaInvalida, CategoriaConProductosActivos,
)
from app.modules.inventario.application.dtos import FiltroCategorias
from app.modules.inventario.application.ports.categoria_repository import CategoriaRepository
from app.shared.responses import Page, PageParams, Sort


class ListarCategoriasUseCase:
    def __init__(self, categoria_repo: CategoriaRepository):
        self._repo = categoria_repo

    async def ejecutar(
        self,
        filtro: FiltroCategorias,
        paginacion: PageParams,
        orden: Sort,
        includes: frozenset[str] = frozenset(),
    ) -> Page:
        return await self._repo.listar(filtro, paginacion, orden, includes)


class ObtenerCategoriaUseCase:
    def __init__(self, categoria_repo: CategoriaRepository):
        self._repo = categoria_repo

    async def ejecutar(
        self, categoria_id: UUID, includes: frozenset[str] = frozenset()
    ) -> Categoria:
        categoria = await self._repo.obtener_por_id(categoria_id, includes)
        if not categoria:
            raise CategoriaNoEncontrada(f"No existe la categoría {categoria_id}")
        return categoria


@dataclass
class ActualizarCategoriaInput:
    categoria_id: UUID
    nombre: str | None = None
    categoria_padre_id: UUID | None = None
    cambiar_padre: bool = False


class ActualizarCategoriaUseCase:
    def __init__(self, categoria_repo: CategoriaRepository):
        self._repo = categoria_repo

    async def ejecutar(self, data: ActualizarCategoriaInput) -> Categoria:
        categoria = await self._repo.obtener_por_id(data.categoria_id)
        if not categoria:
            raise CategoriaNoEncontrada(f"No existe la categoría {data.categoria_id}")

        if data.cambiar_padre and data.categoria_padre_id is not None:
            await self._validar_sin_ciclo(data.categoria_id, data.categoria_padre_id)

        categoria.actualizar(
            nombre=data.nombre,
            categoria_padre_id=data.categoria_padre_id,
            cambiar_padre=data.cambiar_padre,
        )
        await self._repo.actualizar(categoria)
        return categoria

    async def _validar_sin_ciclo(self, categoria_id: UUID, nuevo_padre_id: UUID) -> None:
        if nuevo_padre_id == categoria_id:
            raise JerarquiaCategoriaInvalida("Una categoría no puede ser su propia categoría padre.")
        actual: UUID | None = nuevo_padre_id
        visitados: set[UUID] = set()
        while actual is not None:
            if actual == categoria_id:
                raise JerarquiaCategoriaInvalida(
                    "El cambio de categoría padre genera un ciclo en la jerarquía."
                )
            if actual in visitados:
                break  # ciclo preexistente ajeno a esta categoría; no lo empeora
            visitados.add(actual)
            padre = await self._repo.obtener_por_id(actual)
            if padre is None:
                raise CategoriaNoEncontrada(f"No existe la categoría padre {actual}")
            actual = padre.categoria_padre_id


class DesactivarCategoriaUseCase:
    def __init__(self, categoria_repo: CategoriaRepository):
        self._repo = categoria_repo

    async def ejecutar(self, categoria_id: UUID) -> Categoria:
        categoria = await self._repo.obtener_por_id(categoria_id)
        if not categoria:
            raise CategoriaNoEncontrada(f"No existe la categoría {categoria_id}")
        if await self._repo.tiene_productos_activos(categoria_id):
            raise CategoriaConProductosActivos(
                "No se puede desactivar una categoría con productos activos asociados; "
                "reasigná o desactivá esos productos primero."
            )
        categoria.desactivar()
        await self._repo.actualizar(categoria)
        return categoria
