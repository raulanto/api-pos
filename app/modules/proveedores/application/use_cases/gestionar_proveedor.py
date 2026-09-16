from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.exc import IntegrityError

from app.modules.proveedores.domain.entities import Proveedor
from app.modules.proveedores.domain.value_objects import TipoPersona, CondicionesPago
from app.modules.proveedores.domain.exceptions import (
    ProveedorNoEncontrado, CodigoProveedorEnUso,
)
from app.modules.proveedores.application.ports.proveedor_repository import ProveedorRepository
from app.modules.proveedores.application.dtos import FiltroProveedores
from app.shared.responses import Page, PageParams, Sort


def _traducir_integridad(error: IntegrityError, codigo: str) -> Exception:
    detalle = str(getattr(error, "orig", error)).lower()
    if "codigo" in detalle:
        return CodigoProveedorEnUso(f"Ya existe un proveedor activo con el código '{codigo}'")
    raise error


@dataclass
class CrearProveedorInput:
    codigo: str
    razon_social: str
    tipo_persona: TipoPersona
    condiciones_pago: CondicionesPago
    dias_credito: int | None = None
    nombre_comercial: str | None = None
    rfc: str | None = None
    moneda: str = "MXN"
    contacto_principal: str | None = None
    telefono: str | None = None
    email: str | None = None
    direccion_calle: str | None = None
    direccion_numero: str | None = None
    direccion_colonia: str | None = None
    direccion_ciudad: str | None = None
    direccion_estado: str | None = None
    direccion_codigo_postal: str | None = None
    notas: str | None = None


class CrearProveedorUseCase:
    def __init__(self, repo: ProveedorRepository):
        self._repo = repo

    async def ejecutar(self, data: CrearProveedorInput) -> Proveedor:
        if await self._repo.buscar_por_codigo(data.codigo):
            raise CodigoProveedorEnUso(
                f"Ya existe un proveedor activo con el código '{data.codigo}'"
            )
        proveedor = Proveedor.crear(
            codigo=data.codigo, razon_social=data.razon_social,
            tipo_persona=data.tipo_persona, condiciones_pago=data.condiciones_pago,
            dias_credito=data.dias_credito, nombre_comercial=data.nombre_comercial,
            rfc=data.rfc, moneda=data.moneda, contacto_principal=data.contacto_principal,
            telefono=data.telefono, email=data.email,
            direccion_calle=data.direccion_calle, direccion_numero=data.direccion_numero,
            direccion_colonia=data.direccion_colonia, direccion_ciudad=data.direccion_ciudad,
            direccion_estado=data.direccion_estado,
            direccion_codigo_postal=data.direccion_codigo_postal, notas=data.notas,
        )
        try:
            await self._repo.guardar(proveedor)
        except IntegrityError as e:
            raise _traducir_integridad(e, data.codigo)
        return proveedor


@dataclass
class ActualizarProveedorInput:
    proveedor_id: UUID
    razon_social: str | None = None
    tipo_persona: TipoPersona | None = None
    condiciones_pago: CondicionesPago | None = None
    dias_credito: int | None = None
    cambiar_dias_credito: bool = False
    moneda: str | None = None
    nombre_comercial: str | None = None
    cambiar_nombre_comercial: bool = False
    rfc: str | None = None
    cambiar_rfc: bool = False
    contacto_principal: str | None = None
    cambiar_contacto_principal: bool = False
    telefono: str | None = None
    cambiar_telefono: bool = False
    email: str | None = None
    cambiar_email: bool = False
    notas: str | None = None
    cambiar_notas: bool = False
    direccion_calle: str | None = None
    direccion_numero: str | None = None
    direccion_colonia: str | None = None
    direccion_ciudad: str | None = None
    direccion_estado: str | None = None
    direccion_codigo_postal: str | None = None


class ActualizarProveedorUseCase:
    def __init__(self, repo: ProveedorRepository):
        self._repo = repo

    async def ejecutar(self, data: ActualizarProveedorInput) -> Proveedor:
        proveedor = await self._repo.obtener_por_id(data.proveedor_id)
        if proveedor is None:
            raise ProveedorNoEncontrado(f"No existe el proveedor {data.proveedor_id}")
        proveedor.actualizar(
            razon_social=data.razon_social, tipo_persona=data.tipo_persona,
            condiciones_pago=data.condiciones_pago, dias_credito=data.dias_credito,
            cambiar_dias_credito=data.cambiar_dias_credito, moneda=data.moneda,
            nombre_comercial=data.nombre_comercial,
            cambiar_nombre_comercial=data.cambiar_nombre_comercial,
            rfc=data.rfc, cambiar_rfc=data.cambiar_rfc,
            contacto_principal=data.contacto_principal,
            cambiar_contacto_principal=data.cambiar_contacto_principal,
            telefono=data.telefono, cambiar_telefono=data.cambiar_telefono,
            email=data.email, cambiar_email=data.cambiar_email,
            notas=data.notas, cambiar_notas=data.cambiar_notas,
            direccion_calle=data.direccion_calle, direccion_numero=data.direccion_numero,
            direccion_colonia=data.direccion_colonia, direccion_ciudad=data.direccion_ciudad,
            direccion_estado=data.direccion_estado,
            direccion_codigo_postal=data.direccion_codigo_postal,
        )
        await self._repo.actualizar(proveedor)
        return proveedor


class DesactivarProveedorUseCase:
    def __init__(self, repo: ProveedorRepository):
        self._repo = repo

    async def ejecutar(self, proveedor_id: UUID) -> Proveedor:
        proveedor = await self._repo.obtener_por_id(proveedor_id)
        if proveedor is None:
            raise ProveedorNoEncontrado(f"No existe el proveedor {proveedor_id}")
        proveedor.desactivar()
        await self._repo.actualizar(proveedor)
        return proveedor


class ReactivarProveedorUseCase:
    def __init__(self, repo: ProveedorRepository):
        self._repo = repo

    async def ejecutar(self, proveedor_id: UUID) -> Proveedor:
        proveedor = await self._repo.obtener_por_id(proveedor_id)
        if proveedor is None:
            raise ProveedorNoEncontrado(f"No existe el proveedor {proveedor_id}")
        if proveedor.activo:
            return proveedor
        conflicto = await self._repo.buscar_por_codigo(proveedor.codigo)
        if conflicto and conflicto.id != proveedor.id:
            raise CodigoProveedorEnUso(
                f"Ya existe un proveedor activo con el código '{proveedor.codigo}'; "
                "no se puede reactivar este."
            )
        proveedor.activar()
        await self._repo.actualizar(proveedor)
        return proveedor


class ObtenerProveedorUseCase:
    def __init__(self, repo: ProveedorRepository):
        self._repo = repo

    async def ejecutar(self, proveedor_id: UUID) -> Proveedor:
        proveedor = await self._repo.obtener_por_id(proveedor_id)
        if proveedor is None:
            raise ProveedorNoEncontrado(f"No existe el proveedor {proveedor_id}")
        return proveedor


class ListarProveedoresUseCase:
    def __init__(self, repo: ProveedorRepository):
        self._repo = repo

    async def ejecutar(self, filtro: FiltroProveedores, paginacion: PageParams, orden: Sort) -> Page:
        return await self._repo.listar(filtro, paginacion, orden)
