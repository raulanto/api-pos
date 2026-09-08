from dataclasses import dataclass
from uuid import UUID

from app.modules.ventas.domain.entities import Caja
from app.modules.ventas.domain.exceptions import CajaNoEncontrada
from app.modules.ventas.application.ports.caja_repository import CajaRepository


class NombreCajaEnUso(Exception):
    """Otra caja activa de la sucursal ya usa ese nombre."""
    pass


@dataclass
class CrearCajaInput:
    sucursal_id: UUID
    nombre: str


class CrearCajaUseCase:
    def __init__(self, repo: CajaRepository):
        self._repo = repo

    async def ejecutar(self, data: CrearCajaInput) -> Caja:
        caja = Caja.crear(sucursal_id=data.sucursal_id, nombre=data.nombre)
        if await self._repo.nombre_en_uso(caja.sucursal_id, caja.nombre):
            raise NombreCajaEnUso(
                f"Ya hay una caja activa llamada '{caja.nombre}' en esta sucursal."
            )
        await self._repo.guardar(caja)
        return caja


class ListarCajasUseCase:
    def __init__(self, repo: CajaRepository):
        self._repo = repo

    async def ejecutar(
        self, sucursal_id: UUID, incluir_inactivas: bool = False
    ) -> list[Caja]:
        return await self._repo.listar(sucursal_id, incluir_inactivas)


class RenombrarCajaUseCase:
    def __init__(self, repo: CajaRepository):
        self._repo = repo

    async def ejecutar(self, caja_id: UUID, nombre: str) -> Caja:
        caja = await self._repo.obtener_por_id(caja_id)
        if caja is None:
            raise CajaNoEncontrada(f"No existe la caja {caja_id}")
        caja.renombrar(nombre)
        if await self._repo.nombre_en_uso(caja.sucursal_id, caja.nombre, excluir_id=caja.id):
            raise NombreCajaEnUso(
                f"Ya hay una caja activa llamada '{caja.nombre}' en esta sucursal."
            )
        await self._repo.actualizar(caja)
        return caja


class DesactivarCajaUseCase:
    def __init__(self, repo: CajaRepository):
        self._repo = repo

    async def ejecutar(self, caja_id: UUID) -> Caja:
        caja = await self._repo.obtener_por_id(caja_id)
        if caja is None:
            raise CajaNoEncontrada(f"No existe la caja {caja_id}")
        caja.desactivar()
        await self._repo.actualizar(caja)
        return caja


class ReactivarCajaUseCase:
    def __init__(self, repo: CajaRepository):
        self._repo = repo

    async def ejecutar(self, caja_id: UUID) -> Caja:
        caja = await self._repo.obtener_por_id(caja_id)
        if caja is None:
            raise CajaNoEncontrada(f"No existe la caja {caja_id}")
        if await self._repo.nombre_en_uso(caja.sucursal_id, caja.nombre, excluir_id=caja.id):
            raise NombreCajaEnUso(
                f"Otra caja activa ya usa el nombre '{caja.nombre}'; renombrá o "
                "desactivá esa antes de reactivar."
            )
        caja.reactivar()
        await self._repo.actualizar(caja)
        return caja
