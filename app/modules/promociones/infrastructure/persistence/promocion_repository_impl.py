from datetime import datetime
from uuid import UUID

from sqlalchemy import select, func, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.promociones.application.ports.promocion_repository import PromocionRepository
from app.modules.promociones.application.dtos import FiltroPromociones
from app.modules.promociones.domain.entities import Promocion
from app.modules.promociones.infrastructure.persistence.orm_models import PromocionORM
from app.modules.promociones.infrastructure.persistence.mappers import (
    to_domain_promocion, to_orm_objetivo,
)
from app.shared.responses import Page, PageParams, Sort

_P = PromocionORM


class SqlAlchemyPromocionRepository(PromocionRepository):
    _ORDEN = {
        "nombre": _P.nombre,
        "prioridad": _P.prioridad,
        "created_at": _P.created_at,
    }

    def __init__(self, db: AsyncSession):
        self._db = db

    async def obtener_por_id(self, promocion_id: UUID) -> Promocion | None:
        orm = (await self._db.execute(
            select(_P).options(selectinload(_P.objetivos)).where(_P.id == promocion_id)
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
            cond.append(or_(_P.sucursal_id == filtro.sucursal_id, _P.sucursal_id.is_(None)))
        if filtro.busqueda:
            cond.append(_P.nombre.ilike(f"%{filtro.busqueda.strip()}%"))

        col = self._ORDEN.get(orden.field, _P.prioridad)
        orden_expr = col.desc() if orden.descending else col.asc()

        total = await self._db.scalar(select(func.count()).select_from(_P).where(*cond))
        filas = (await self._db.execute(
            select(_P).options(selectinload(_P.objetivos)).where(*cond)
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
            or_(_P.sucursal_id.is_(None), _P.sucursal_id == sucursal_id),
        )
        filas = (await self._db.execute(
            select(_P).options(selectinload(_P.objetivos)).where(cond)
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
            sucursal_id=promocion.sucursal_id,
            vigente_desde=promocion.vigente_desde,
            vigente_hasta=promocion.vigente_hasta,
            nxm_lleva=promocion.nxm_lleva,
            nxm_paga=promocion.nxm_paga,
            descuento_pct=promocion.descuento_pct,
            precio_fijo=promocion.precio_fijo,
            cantidad_minima=promocion.cantidad_minima,
        )
        orm.objetivos = [to_orm_objetivo(o) for o in promocion.objetivos]
        self._db.add(orm)
        await self._db.flush()
        return promocion

    async def actualizar(self, promocion: Promocion) -> None:
        orm = (await self._db.execute(
            select(_P).options(selectinload(_P.objetivos)).where(_P.id == promocion.id)
        )).scalars().first()
        orm.nombre = promocion.nombre
        orm.tipo = promocion.tipo.value
        orm.activo = promocion.activo
        orm.prioridad = promocion.prioridad
        orm.sucursal_id = promocion.sucursal_id
        orm.vigente_desde = promocion.vigente_desde
        orm.vigente_hasta = promocion.vigente_hasta
        orm.nxm_lleva = promocion.nxm_lleva
        orm.nxm_paga = promocion.nxm_paga
        orm.descuento_pct = promocion.descuento_pct
        orm.precio_fijo = promocion.precio_fijo
        orm.cantidad_minima = promocion.cantidad_minima
        # `cascade="all, delete-orphan"`: reasignar la colección borra los que
        # ya no están e inserta los nuevos.
        orm.objetivos = [to_orm_objetivo(o) for o in promocion.objetivos]
        await self._db.flush()
