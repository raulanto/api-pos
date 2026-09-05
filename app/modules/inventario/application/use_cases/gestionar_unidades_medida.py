"""Casos de uso del catálogo de unidades de medida (`unidad_medida`).

Reglas:
- `codigo` único (se normaliza a minúsculas y sin espacios).
- `decimales` entre 0 y 6.
- No se puede desactivar una unidad que esté en uso por productos o
  presentaciones (`UnidadMedidaEnUso`).
"""
from dataclasses import dataclass
from uuid import UUID

from app.modules.inventario.domain.entities import UnidadMedida
from app.modules.inventario.domain.value_objects import TipoMagnitud
from app.modules.inventario.domain.exceptions import (
    UnidadMedidaNoEncontrada, UnidadMedidaDuplicada, UnidadMedidaEnUso,
)
from app.modules.inventario.application.ports.unidad_medida_repository import (
    UnidadMedidaRepository,
)


class ListarUnidadesMedidaUseCase:
    def __init__(self, repo: UnidadMedidaRepository):
        self._repo = repo

    async def ejecutar(self, incluir_inactivas: bool = False) -> list[UnidadMedida]:
        return await self._repo.listar(incluir_inactivas)


class ObtenerUnidadMedidaUseCase:
    def __init__(self, repo: UnidadMedidaRepository):
        self._repo = repo

    async def ejecutar(self, unidad_id: UUID) -> UnidadMedida:
        unidad = await self._repo.obtener(unidad_id)
        if unidad is None:
            raise UnidadMedidaNoEncontrada(f"No existe la unidad de medida {unidad_id}")
        return unidad


@dataclass
class CrearUnidadMedidaInput:
    codigo: str
    nombre: str
    tipo_magnitud: TipoMagnitud
    decimales: int = 0


class CrearUnidadMedidaUseCase:
    def __init__(self, repo: UnidadMedidaRepository):
        self._repo = repo

    async def ejecutar(self, data: CrearUnidadMedidaInput) -> UnidadMedida:
        codigo = data.codigo.strip().lower()
        if await self._repo.obtener_por_codigo(codigo) is not None:
            raise UnidadMedidaDuplicada(f"Ya existe una unidad con el código '{codigo}'.")
        unidad = UnidadMedida.crear(
            codigo=codigo,
            nombre=data.nombre,
            tipo_magnitud=data.tipo_magnitud,
            decimales=data.decimales,
        )
        await self._repo.crear(unidad)
        return unidad


@dataclass
class ActualizarUnidadMedidaInput:
    unidad_id: UUID
    nombre: str | None = None
    tipo_magnitud: TipoMagnitud | None = None
    decimales: int | None = None


class ActualizarUnidadMedidaUseCase:
    def __init__(self, repo: UnidadMedidaRepository):
        self._repo = repo

    async def ejecutar(self, data: ActualizarUnidadMedidaInput) -> UnidadMedida:
        unidad = await self._repo.obtener(data.unidad_id)
        if unidad is None:
            raise UnidadMedidaNoEncontrada(
                f"No existe la unidad de medida {data.unidad_id}"
            )
        unidad.actualizar(
            nombre=data.nombre,
            tipo_magnitud=data.tipo_magnitud,
            decimales=data.decimales,
        )
        await self._repo.actualizar(unidad)
        return unidad


class DesactivarUnidadMedidaUseCase:
    def __init__(self, repo: UnidadMedidaRepository):
        self._repo = repo

    async def ejecutar(self, unidad_id: UUID) -> None:
        unidad = await self._repo.obtener(unidad_id)
        if unidad is None:
            raise UnidadMedidaNoEncontrada(f"No existe la unidad de medida {unidad_id}")
        if await self._repo.esta_en_uso(unidad_id):
            raise UnidadMedidaEnUso(
                "La unidad está asignada a productos o presentaciones; reasignalos "
                "antes de desactivarla."
            )
        unidad.desactivar()
        await self._repo.actualizar(unidad)


class ReactivarUnidadMedidaUseCase:
    def __init__(self, repo: UnidadMedidaRepository):
        self._repo = repo

    async def ejecutar(self, unidad_id: UUID) -> UnidadMedida:
        unidad = await self._repo.obtener(unidad_id)
        if unidad is None:
            raise UnidadMedidaNoEncontrada(f"No existe la unidad de medida {unidad_id}")
        unidad.activar()
        await self._repo.actualizar(unidad)
        return unidad
