"""CRUD de promociones. La coherencia de params por `tipo` la valida la entidad
(`Promocion._validar` -> `PromocionInvalida`); acá solo se resuelve la unicidad
de `nombre` y la carga de objetivos."""
from dataclasses import dataclass, field
from datetime import datetime, time
from decimal import Decimal
from uuid import UUID, uuid4

from app.modules.promociones.domain.entities import (
    Promocion, PromocionObjetivo, TipoPromocion,
)
from app.modules.promociones.domain.exceptions import (
    PromocionNoEncontrada, PromocionInvalida,
)
from app.modules.promociones.application.dtos import FiltroPromociones
from app.modules.promociones.application.ports.promocion_repository import PromocionRepository
from app.shared.responses import Page, PageParams, Sort


@dataclass
class ObjetivoInput:
    producto_id: UUID | None = None
    producto_unidad_id: UUID | None = None
    categoria_id: UUID | None = None


def _objetivos(entradas: list[ObjetivoInput]) -> list[PromocionObjetivo]:
    if not entradas:
        raise PromocionInvalida("Indicá al menos un producto, presentación o categoría objetivo.")
    out = []
    for e in entradas:
        puestos = sum(x is not None for x in (e.producto_id, e.producto_unidad_id, e.categoria_id))
        if puestos != 1:
            raise PromocionInvalida(
                "Cada objetivo lleva exactamente uno de `producto_id`, "
                "`producto_unidad_id` o `categoria_id`."
            )
        out.append(PromocionObjetivo(
            id=uuid4(), promocion_id=uuid4(),  # promocion_id lo fija Promocion.crear/actualizar
            producto_id=e.producto_id, producto_unidad_id=e.producto_unidad_id,
            categoria_id=e.categoria_id,
        ))
    return out


# --------------------------------------------------------------------------- #
class ListarPromocionesUseCase:
    def __init__(self, repo: PromocionRepository):
        self._repo = repo

    async def ejecutar(
        self, filtro: FiltroPromociones, paginacion: PageParams, orden: Sort
    ) -> Page:
        return await self._repo.listar(filtro, paginacion, orden)


class ObtenerPromocionUseCase:
    def __init__(self, repo: PromocionRepository):
        self._repo = repo

    async def ejecutar(self, promocion_id: UUID) -> Promocion:
        promo = await self._repo.obtener_por_id(promocion_id)
        if promo is None:
            raise PromocionNoEncontrada(f"No existe la promoción {promocion_id}")
        return promo


# --------------------------------------------------------------------------- #
@dataclass
class CrearPromocionInput:
    nombre: str
    tipo: TipoPromocion
    objetivos: list[ObjetivoInput] = field(default_factory=list)
    prioridad: int = 100
    activo: bool = True
    sucursales: list[UUID] = field(default_factory=list)
    vigente_desde: datetime | None = None
    vigente_hasta: datetime | None = None
    hora_desde: time | None = None
    hora_hasta: time | None = None
    dias_semana: int | None = None
    nxm_lleva: int | None = None
    nxm_paga: int | None = None
    descuento_pct: Decimal | None = None
    precio_fijo: Decimal | None = None
    cantidad_minima: Decimal | None = None
    combinable: bool = False
    tope_descuento: Decimal | None = None
    monto_minimo_compra: Decimal | None = None
    metodo_pago_requerido: str | None = None
    cliente_segmento: str | None = None
    requiere_cupon: bool = False


class CrearPromocionUseCase:
    def __init__(self, repo: PromocionRepository):
        self._repo = repo

    async def ejecutar(self, data: CrearPromocionInput) -> Promocion:
        nombre = data.nombre.strip()
        if await self._repo.existe_nombre(nombre):
            raise PromocionInvalida(f"Ya existe una promoción con nombre '{nombre}'.")
        promo = Promocion.crear(
            nombre=nombre, tipo=data.tipo, objetivos=_objetivos(data.objetivos),
            prioridad=data.prioridad, activo=data.activo, sucursales=data.sucursales,
            vigente_desde=data.vigente_desde, vigente_hasta=data.vigente_hasta,
            hora_desde=data.hora_desde, hora_hasta=data.hora_hasta,
            dias_semana=data.dias_semana,
            nxm_lleva=data.nxm_lleva, nxm_paga=data.nxm_paga,
            descuento_pct=data.descuento_pct, precio_fijo=data.precio_fijo,
            cantidad_minima=data.cantidad_minima,
            combinable=data.combinable, tope_descuento=data.tope_descuento,
            monto_minimo_compra=data.monto_minimo_compra,
            metodo_pago_requerido=data.metodo_pago_requerido,
            cliente_segmento=data.cliente_segmento,
            requiere_cupon=data.requiere_cupon,
        )
        return await self._repo.crear(promo)


# --------------------------------------------------------------------------- #
@dataclass
class ActualizarPromocionInput:
    promocion_id: UUID
    nombre: str | None = None
    prioridad: int | None = None
    activo: bool | None = None
    sucursales: list[UUID] | None = None
    cambiar_sucursales: bool = False
    vigente_desde: datetime | None = None
    vigente_hasta: datetime | None = None
    cambiar_vigencia: bool = False
    hora_desde: time | None = None
    hora_hasta: time | None = None
    dias_semana: int | None = None
    cambiar_horario: bool = False
    tipo: TipoPromocion | None = None
    combinable: bool | None = None
    tope_descuento: Decimal | None = None
    monto_minimo_compra: Decimal | None = None
    cambiar_topes: bool = False
    metodo_pago_requerido: str | None = None
    cliente_segmento: str | None = None
    requiere_cupon: bool | None = None
    cambiar_condiciones: bool = False
    nxm_lleva: int | None = None
    nxm_paga: int | None = None
    descuento_pct: Decimal | None = None
    precio_fijo: Decimal | None = None
    cantidad_minima: Decimal | None = None
    cambiar_cantidad_minima: bool = False
    objetivos: list[ObjetivoInput] | None = None


class ActualizarPromocionUseCase:
    def __init__(self, repo: PromocionRepository):
        self._repo = repo

    async def ejecutar(self, data: ActualizarPromocionInput) -> Promocion:
        promo = await self._repo.obtener_por_id(data.promocion_id)
        if promo is None:
            raise PromocionNoEncontrada(f"No existe la promoción {data.promocion_id}")
        if data.nombre is not None:
            nombre = data.nombre.strip()
            if await self._repo.existe_nombre(nombre, excluir_id=promo.id):
                raise PromocionInvalida(f"Ya existe una promoción con nombre '{nombre}'.")
        promo.actualizar(
            nombre=data.nombre, prioridad=data.prioridad, activo=data.activo,
            sucursales=data.sucursales, cambiar_sucursales=data.cambiar_sucursales,
            vigente_desde=data.vigente_desde, vigente_hasta=data.vigente_hasta,
            cambiar_vigencia=data.cambiar_vigencia,
            hora_desde=data.hora_desde, hora_hasta=data.hora_hasta,
            dias_semana=data.dias_semana, cambiar_horario=data.cambiar_horario,
            metodo_pago_requerido=data.metodo_pago_requerido,
            cliente_segmento=data.cliente_segmento,
            requiere_cupon=data.requiere_cupon,
            cambiar_condiciones=data.cambiar_condiciones,
            combinable=data.combinable, tope_descuento=data.tope_descuento,
            monto_minimo_compra=data.monto_minimo_compra, cambiar_topes=data.cambiar_topes,
            tipo=data.tipo, nxm_lleva=data.nxm_lleva, nxm_paga=data.nxm_paga,
            descuento_pct=data.descuento_pct, precio_fijo=data.precio_fijo,
            cantidad_minima=data.cantidad_minima,
            cambiar_cantidad_minima=data.cambiar_cantidad_minima,
            objetivos=_objetivos(data.objetivos) if data.objetivos is not None else None,
        )
        await self._repo.actualizar(promo)
        return promo


# --------------------------------------------------------------------------- #
class DesactivarPromocionUseCase:
    def __init__(self, repo: PromocionRepository):
        self._repo = repo

    async def ejecutar(self, promocion_id: UUID) -> Promocion:
        promo = await self._repo.obtener_por_id(promocion_id)
        if promo is None:
            raise PromocionNoEncontrada(f"No existe la promoción {promocion_id}")
        promo.desactivar()
        await self._repo.actualizar(promo)
        return promo


class ReactivarPromocionUseCase:
    def __init__(self, repo: PromocionRepository):
        self._repo = repo

    async def ejecutar(self, promocion_id: UUID) -> Promocion:
        promo = await self._repo.obtener_por_id(promocion_id)
        if promo is None:
            raise PromocionNoEncontrada(f"No existe la promoción {promocion_id}")
        promo.activar()
        await self._repo.actualizar(promo)
        return promo
