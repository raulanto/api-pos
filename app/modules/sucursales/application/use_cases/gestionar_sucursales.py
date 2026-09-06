"""Casos de uso del módulo sucursales (CRUD + soft-delete + jerarquía).

Reglas:
- `nombre` único case-insensitive (activas e inactivas); `codigo` único si viene.
- `sucursal_padre_id` debe existir y no puede apuntar a sí misma ni crear ciclo.
- No se puede desactivar una sucursal con usuarios activos asignados.
- La baja es lógica; hay endpoint de reactivación.
"""
from dataclasses import dataclass
from datetime import time
from decimal import Decimal
from uuid import UUID

from app.modules.sucursales.domain.entities import Sucursal, TipoSucursal
from app.modules.sucursales.domain.exceptions import (
    SucursalNoEncontrada, NombreSucursalDuplicado, CodigoSucursalDuplicado,
    SucursalConUsuariosActivos, SucursalPadreNoEncontrada, JerarquiaSucursalInvalida,
)
from app.modules.sucursales.application.dtos import FiltroSucursales
from app.modules.sucursales.application.ports.sucursal_repository import SucursalRepository
from app.shared.responses import Page, PageParams, Sort

_MAX_SALTOS_JERARQUIA = 20


async def _validar_padre(
    repo: SucursalRepository, sucursal_id: UUID | None, padre_id: UUID | None,
) -> None:
    """El padre debe existir y no puede haber ciclo (subiendo por `padre`)."""
    if padre_id is None:
        return
    if sucursal_id is not None and padre_id == sucursal_id:
        raise JerarquiaSucursalInvalida("Una sucursal no puede ser su propia padre.")
    actual = await repo.obtener_por_id(padre_id)
    if actual is None:
        raise SucursalPadreNoEncontrada(f"No existe la sucursal padre {padre_id}")
    saltos = 0
    while actual is not None:
        if sucursal_id is not None and actual.id == sucursal_id:
            raise JerarquiaSucursalInvalida(
                "El cambio de padre genera un ciclo en la jerarquía."
            )
        if actual.sucursal_padre_id is None:
            break
        saltos += 1
        if saltos > _MAX_SALTOS_JERARQUIA:
            raise JerarquiaSucursalInvalida("Jerarquía demasiado profunda o con ciclo.")
        actual = await repo.obtener_por_id(actual.sucursal_padre_id)


# --------------------------------------------------------------------------- #
class ListarSucursalesUseCase:
    def __init__(self, sucursal_repo: SucursalRepository):
        self._repo = sucursal_repo

    async def ejecutar(
        self, filtro: FiltroSucursales, paginacion: PageParams, orden: Sort
    ) -> Page:
        return await self._repo.listar(filtro, paginacion, orden)


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
    tipo: TipoSucursal = TipoSucursal.TIENDA
    codigo: str | None = None
    descripcion: str | None = None
    colonia: str | None = None
    ciudad: str | None = None
    estado: str | None = None
    codigo_postal: str | None = None
    pais: str | None = "México"
    latitud: Decimal | None = None
    longitud: Decimal | None = None
    email: str | None = None
    horario_apertura: time | None = None
    horario_cierre: time | None = None
    sucursal_padre_id: UUID | None = None
    permite_ventas: bool = True


class CrearSucursalUseCase:
    def __init__(self, sucursal_repo: SucursalRepository):
        self._repo = sucursal_repo

    async def ejecutar(self, data: CrearSucursalInput) -> Sucursal:
        nombre = data.nombre.strip()
        if await self._repo.obtener_por_nombre(nombre) is not None:
            raise NombreSucursalDuplicado(f"Ya existe una sucursal con nombre '{nombre}'")
        codigo = data.codigo.strip() if data.codigo else None
        if codigo and await self._repo.obtener_por_codigo(codigo) is not None:
            raise CodigoSucursalDuplicado(f"Ya existe una sucursal con código '{codigo}'")
        await _validar_padre(self._repo, None, data.sucursal_padre_id)

        sucursal = Sucursal.crear(
            nombre=nombre,
            direccion=data.direccion.strip(),
            telefono=data.telefono.strip(),
            tipo=data.tipo,
            codigo=codigo,
            descripcion=data.descripcion,
            colonia=data.colonia,
            ciudad=data.ciudad,
            estado=data.estado,
            codigo_postal=data.codigo_postal,
            pais=data.pais,
            latitud=data.latitud,
            longitud=data.longitud,
            email=data.email,
            horario_apertura=data.horario_apertura,
            horario_cierre=data.horario_cierre,
            sucursal_padre_id=data.sucursal_padre_id,
            permite_ventas=data.permite_ventas,
        )
        return await self._repo.crear(sucursal)


# --------------------------------------------------------------------------- #
@dataclass
class ActualizarSucursalInput:
    sucursal_id: UUID
    nombre: str | None = None
    direccion: str | None = None
    telefono: str | None = None
    tipo: TipoSucursal | None = None
    permite_ventas: bool | None = None
    codigo: str | None = None
    cambiar_codigo: bool = False
    descripcion: str | None = None
    cambiar_descripcion: bool = False
    colonia: str | None = None
    cambiar_colonia: bool = False
    ciudad: str | None = None
    cambiar_ciudad: bool = False
    estado: str | None = None
    cambiar_estado: bool = False
    codigo_postal: str | None = None
    cambiar_codigo_postal: bool = False
    pais: str | None = None
    cambiar_pais: bool = False
    latitud: Decimal | None = None
    longitud: Decimal | None = None
    cambiar_geo: bool = False
    email: str | None = None
    cambiar_email: bool = False
    horario_apertura: time | None = None
    horario_cierre: time | None = None
    cambiar_horario: bool = False
    sucursal_padre_id: UUID | None = None
    cambiar_padre: bool = False


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

        if data.cambiar_codigo and data.codigo:
            codigo = data.codigo.strip()
            existente = await self._repo.obtener_por_codigo(codigo)
            if existente is not None and existente.id != sucursal.id:
                raise CodigoSucursalDuplicado(f"Ya existe una sucursal con código '{codigo}'")

        if data.cambiar_padre:
            await _validar_padre(self._repo, sucursal.id, data.sucursal_padre_id)

        sucursal.actualizar(
            nombre=nombre,
            direccion=data.direccion.strip() if data.direccion is not None else None,
            telefono=data.telefono.strip() if data.telefono is not None else None,
            tipo=data.tipo,
            permite_ventas=data.permite_ventas,
            codigo=data.codigo, cambiar_codigo=data.cambiar_codigo,
            descripcion=data.descripcion, cambiar_descripcion=data.cambiar_descripcion,
            colonia=data.colonia, cambiar_colonia=data.cambiar_colonia,
            ciudad=data.ciudad, cambiar_ciudad=data.cambiar_ciudad,
            estado=data.estado, cambiar_estado=data.cambiar_estado,
            codigo_postal=data.codigo_postal, cambiar_codigo_postal=data.cambiar_codigo_postal,
            pais=data.pais, cambiar_pais=data.cambiar_pais,
            latitud=data.latitud, longitud=data.longitud, cambiar_geo=data.cambiar_geo,
            email=data.email, cambiar_email=data.cambiar_email,
            horario_apertura=data.horario_apertura, horario_cierre=data.horario_cierre,
            cambiar_horario=data.cambiar_horario,
            sucursal_padre_id=data.sucursal_padre_id, cambiar_padre=data.cambiar_padre,
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
