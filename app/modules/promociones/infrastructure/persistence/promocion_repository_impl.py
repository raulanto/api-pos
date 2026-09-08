from datetime import datetime
from uuid import UUID

from sqlalchemy import select, func, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.promociones.application.ports.promocion_repository import PromocionRepository
from app.modules.promociones.application.dtos import FiltroPromociones
from app.modules.promociones.domain.entities import Promocion
from app.modules.promociones.infrastructure.persistence.orm_models import (
    PromocionORM, PromocionSucursalORM,
)
from app.modules.promociones.infrastructure.persistence.mappers import (
    to_domain_promocion, to_orm_objetivo,
)
from app.shared.responses import Page, PageParams, Sort

_P = PromocionORM
_PS = PromocionSucursalORM


def _cond_sucursal(sucursal_id: UUID):
    """La promo aplica a `sucursal_id` si no tiene filas en promocion_sucursal
    (= todas) o si tiene una para esa sucursal."""
    tiene_filas = select(_PS.promocion_id).where(_PS.promocion_id == _P.id).exists()
    coincide = (
        select(_PS.promocion_id)
        .where(_PS.promocion_id == _P.id, _PS.sucursal_id == sucursal_id)
        .exists()
    )
    return or_(~tiene_filas, coincide)


class SqlAlchemyPromocionRepository(PromocionRepository):
    _ORDEN = {
        "nombre": _P.nombre,
        "prioridad": _P.prioridad,
        "created_at": _P.created_at,
    }

    def __init__(self, db: AsyncSession):
        self._db = db

    _OPTS = (selectinload(_P.objetivos), selectinload(_P.sucursales))

    async def obtener_por_id(self, promocion_id: UUID) -> Promocion | None:
        orm = (await self._db.execute(
            select(_P).options(*self._OPTS).where(_P.id == promocion_id)
        )).scalars().first()
        return to_domain_promocion(orm) if orm else None

    async def listar(
        self, filtro: FiltroPromociones, paginacion: PageParams, orden: Sort
    ) -> Page:
        cond = []
        if filtro.activo is not None:
            cond.append(_P.activo == filtro.activo)
        if filtro.tipo is not None:
            cond.append(_P.tipo == filtro.tipo.value)
        if filtro.sucursal_id is not None:
            cond.append(_cond_sucursal(filtro.sucursal_id))
        if filtro.busqueda:
            cond.append(_P.nombre.ilike(f"%{filtro.busqueda.strip()}%"))

        col = self._ORDEN.get(orden.field, _P.prioridad)
        orden_expr = col.desc() if orden.descending else col.asc()

        total = await self._db.scalar(select(func.count()).select_from(_P).where(*cond))
        filas = (await self._db.execute(
            select(_P).options(*self._OPTS).where(*cond)
            .order_by(orden_expr).limit(paginacion.limit).offset(paginacion.offset)
        )).scalars().all()
        return Page(items=[to_domain_promocion(o) for o in filas], total=int(total or 0))

    async def listar_vigentes(
        self, momento: datetime, sucursal_id: UUID
    ) -> list[Promocion]:
        cond = and_(
            _P.activo.is_(True),
            or_(_P.vigente_desde.is_(None), _P.vigente_desde <= momento),
            or_(_P.vigente_hasta.is_(None), _P.vigente_hasta >= momento),
            _cond_sucursal(sucursal_id),
        )
        filas = (await self._db.execute(
            select(_P).options(*self._OPTS).where(cond)
        )).scalars().all()
        return [to_domain_promocion(o) for o in filas]

    async def existe_nombre(self, nombre: str, excluir_id: UUID | None = None) -> bool:
        cond = [func.lower(_P.nombre) == nombre.strip().lower()]
        if excluir_id is not None:
            cond.append(_P.id != excluir_id)
        total = await self._db.scalar(select(func.count()).select_from(_P).where(*cond))
        return bool(total)

    async def crear(self, promocion: Promocion) -> Promocion:
        orm = _P(
            id=promocion.id,
            nombre=promocion.nombre,
            tipo=promocion.tipo.value,
            activo=promocion.activo,
            prioridad=promocion.prioridad,
            combinable=promocion.combinable,
            tope_descuento=promocion.tope_descuento,
            monto_minimo_compra=promocion.monto_minimo_compra,
            metodo_pago_requerido=promocion.metodo_pago_requerido,
            cliente_segmento=promocion.cliente_segmento,
            requiere_cupon=promocion.requiere_cupon,
            vigente_desde=promocion.vigente_desde,
            vigente_hasta=promocion.vigente_hasta,
            hora_desde=promocion.hora_desde,
            hora_hasta=promocion.hora_hasta,
            dias_semana=promocion.dias_semana,
            nxm_lleva=promocion.nxm_lleva,
            nxm_paga=promocion.nxm_paga,
            descuento_pct=promocion.descuento_pct,
            precio_fijo=promocion.precio_fijo,
            cantidad_minima=promocion.cantidad_minima,
        )
        orm.objetivos = [to_orm_objetivo(o) for o in promocion.objetivos]
        orm.sucursales = [
            _PS(promocion_id=promocion.id, sucursal_id=sid)
            for sid in promocion.sucursales
        ]
        self._db.add(orm)
        await self._db.flush()
        return promocion

    async def actualizar(self, promocion: Promocion) -> None:
        orm = (await self._db.execute(
            select(_P).options(*self._OPTS).where(_P.id == promocion.id)
        )).scalars().first()
        orm.nombre = promocion.nombre
        orm.tipo = promocion.tipo.value
        orm.activo = promocion.activo
        orm.prioridad = promocion.prioridad
        orm.combinable = promocion.combinable
        orm.tope_descuento = promocion.tope_descuento
        orm.monto_minimo_compra = promocion.monto_minimo_compra
        orm.metodo_pago_requerido = promocion.metodo_pago_requerido
        orm.cliente_segmento = promocion.cliente_segmento
        orm.requiere_cupon = promocion.requiere_cupon
        orm.vigente_desde = promocion.vigente_desde
        orm.vigente_hasta = promocion.vigente_hasta
        orm.hora_desde = promocion.hora_desde
        orm.hora_hasta = promocion.hora_hasta
        orm.dias_semana = promocion.dias_semana
        orm.nxm_lleva = promocion.nxm_lleva
        orm.nxm_paga = promocion.nxm_paga
        orm.descuento_pct = promocion.descuento_pct
        orm.precio_fijo = promocion.precio_fijo
        orm.cantidad_minima = promocion.cantidad_minima
        # `cascade="all, delete-orphan"`: reasignar la colección borra los que
        # ya no están e inserta los nuevos.
        orm.objetivos = [to_orm_objetivo(o) for o in promocion.objetivos]
        orm.sucursales = [
            _PS(promocion_id=promocion.id, sucursal_id=sid)
            for sid in promocion.sucursales
        ]
        await self._db.flush()
