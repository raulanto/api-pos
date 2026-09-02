"""Casos de uso del catálogo de sucursales (CRUD con soft-delete).

Reglas de negocio implementadas:
- El nombre de sucursal es único (case-insensitive), entre activas e inactivas.
- No se puede desactivar una sucursal que aún tiene usuarios activos asignados.
- La baja es lógica (`activo = False`); hay endpoint de reactivación.
"""
from dataclasses import dataclass
from uuid import UUID

from app.modules.usuarios.domain.entities import Sucursal
from app.modules.usuarios.domain.exceptions import (
    SucursalNoEncontrada, NombreSucursalDuplicado, SucursalConUsuariosActivos,
)
from app.modules.usuarios.application.dto import FiltroSucursales
from app.modules.usuarios.application.ports.catalogos_repository import SucursalRepository
from app.shared.responses import Page, PageParams, Sort


# --------------------------------------------------------------------------- #
class ListarSucursalesUseCase:
    def __init__(self, sucursal_repo: SucursalRepository):
        self._repo = sucursal_repo

    async def ejecutar(
        self, filtro: FiltroSucursales, paginacion: PageParams, orden: Sort
    ) -> Page:
        return await self._repo.listar(filtro, paginacion, orden)


# --------------------------------------------------------------------------- #
class ObtenerSucursalUseCase:
    def __init__(self, sucursal_repo: SucursalRepository):
        self._repo = sucursal_repo

    async def ejecutar(self, sucursal_id: UUID) -> Sucursal:
        sucursal = await self._repo.obtener_por_id(sucursal_id)
        if sucursal is None:
            raise SucursalNoEncontrada(f"No existe sucursal con id {sucursal_id}")
        return sucursal


# --------------------------------------------------------------------------- #
@dataclass
class CrearSucursalInput:
    nombre: str
    direccion: str
    telefono: str


class CrearSucursalUseCase:
    def __init__(self, sucursal_repo: SucursalRepository):
        self._repo = sucursal_repo

    async def ejecutar(self, data: CrearSucursalInput) -> Sucursal:
        nombre = data.nombre.strip()
        if await self._repo.obtener_por_nombre(nombre) is not None:
            raise NombreSucursalDuplicado(f"Ya existe una sucursal con nombre '{nombre}'")
        sucursal = Sucursal.crear(
            nombre=nombre,
            direccion=data.direccion.strip(),
            telefono=data.telefono.strip(),
        )
        return await self._repo.crear(sucursal)


# --------------------------------------------------------------------------- #
@dataclass
class ActualizarSucursalInput:
    sucursal_id: UUID
    nombre: str | None = None
    direccion: str | None = None
    telefono: str | None = None


class ActualizarSucursalUseCase:
    def __init__(self, sucursal_repo: SucursalRepository):
        self._repo = sucursal_repo

    async def ejecutar(self, data: ActualizarSucursalInput) -> Sucursal:
        sucursal = await self._repo.obtener_por_id(data.sucursal_id)
        if sucursal is None:
            raise SucursalNoEncontrada(f"No existe sucursal con id {data.sucursal_id}")

        nombre = data.nombre.strip() if data.nombre is not None else None
        if nombre is not None:
            existente = await self._repo.obtener_por_nombre(nombre)
            if existente is not None and existente.id != sucursal.id:
                raise NombreSucursalDuplicado(f"Ya existe una sucursal con nombre '{nombre}'")

        sucursal.actualizar(
            nombre=nombre,
            direccion=data.direccion.strip() if data.direccion is not None else None,
            telefono=data.telefono.strip() if data.telefono is not None else None,
        )
        await self._repo.actualizar(sucursal)
        return sucursal


# --------------------------------------------------------------------------- #
class DesactivarSucursalUseCase:
    def __init__(self, sucursal_repo: SucursalRepository):
        self._repo = sucursal_repo

    async def ejecutar(self, sucursal_id: UUID) -> Sucursal:
        sucursal = await self._repo.obtener_por_id(sucursal_id)
        if sucursal is None:
            raise SucursalNoEncontrada(f"No existe sucursal con id {sucursal_id}")
        if await self._repo.tiene_usuarios_activos(sucursal_id):
            raise SucursalConUsuariosActivos(
                "No se puede desactivar una sucursal con usuarios activos asignados; "
                "reasigná o desactivá esos usuarios primero."
            )
        sucursal.desactivar()
        await self._repo.actualizar(sucursal)
        return sucursal


# --------------------------------------------------------------------------- #
class ReactivarSucursalUseCase:
    def __init__(self, sucursal_repo: SucursalRepository):
        self._repo = sucursal_repo

    async def ejecutar(self, sucursal_id: UUID) -> Sucursal:
        sucursal = await self._repo.obtener_por_id(sucursal_id)
        if sucursal is None:
            raise SucursalNoEncontrada(f"No existe sucursal con id {sucursal_id}")
        sucursal.activar()
        await self._repo.actualizar(sucursal)
        return sucursal
