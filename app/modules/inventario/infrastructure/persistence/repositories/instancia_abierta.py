from decimal import Decimal
from uuid import UUID

from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.inventario.application.ports.instancia_abierta_repository import (
    InstanciaAbiertaRepository,
)
from app.modules.inventario.application.dtos import FiltroInstancias
from app.modules.inventario.domain.entities import InstanciaAbierta
from app.modules.inventario.domain.value_objects import EstadoInstancia
from app.modules.inventario.infrastructure.persistence.orm_models import InstanciaAbiertaORM
from app.modules.inventario.infrastructure.persistence.mappers import (
    to_domain_instancia, to_orm_instancia,
)
from app.shared.responses import Page, PageParams, Sort

_IA = InstanciaAbiertaORM
_ABIERTA = EstadoInstancia.ABIERTA.value


class SqlAlchemyInstanciaAbiertaRepository(InstanciaAbiertaRepository):
    def __init__(self, db: AsyncSession):
        self._db = db

    async def crear(self, instancia: InstanciaAbierta) -> None:
        self._db.add(to_orm_instancia(instancia))
        await self._db.flush()

    async def obtener(self, instancia_id: UUID) -> InstanciaAbierta | None:
        orm = await self._db.get(_IA, instancia_id)
        return to_domain_instancia(orm) if orm else None

    async def actualizar(self, instancia: InstanciaAbierta) -> None:
        await self._db.execute(
            update(_IA)
            .where(_IA.id == instancia.id)
            .values(
                producto_unidad_id=instancia.producto_unidad_id,
                lote_id=instancia.lote_id,
                saldo=instancia.saldo,
                estado=instancia.estado.value,
                cerrada_at=instancia.cerrada_at,
                motivo_cierre=instancia.motivo_cierre,
            )
        )
        await self._db.flush()

    _ORDEN = {
        "abierta_at": _IA.abierta_at,
        "saldo": _IA.saldo,
        "created_at": _IA.created_at,
    }

    async def listar(
        self, filtro: FiltroInstancias, paginacion: PageParams, orden: Sort,
    ) -> Page:
        cond = []
        if filtro.producto_id is not None:
            cond.append(_IA.producto_id == filtro.producto_id)
        if filtro.sucursal_id:
            cond.append(_IA.sucursal_id.in_(filtro.sucursal_id))
        if filtro.estado is not None:
            cond.append(_IA.estado == filtro.estado.value)
        if filtro.lote_id is not None:
            cond.append(_IA.lote_id == filtro.lote_id)

        col = self._ORDEN.get(orden.field, _IA.abierta_at)
        orden_expr = col.desc() if orden.descending else col.asc()

        total = await self._db.scalar(
            select(func.count()).select_from(_IA).where(*cond)
        )
        filas = (await self._db.execute(
            select(_IA).where(*cond).order_by(orden_expr)
            .limit(paginacion.limit).offset(paginacion.offset)
        )).scalars().all()
        return Page(
            items=[to_domain_instancia(f) for f in filas], total=int(total or 0)
        )

    async def listar_abiertas(
        self, producto_id: UUID, sucursal_id: UUID,
    ) -> list[InstanciaAbierta]:
        filas = (await self._db.execute(
            select(_IA)
            .where(
                _IA.producto_id == producto_id,
                _IA.sucursal_id == sucursal_id,
                _IA.estado == _ABIERTA,
            )
            .order_by(_IA.abierta_at.asc(), _IA.created_at.asc())
        )).scalars().all()
        return [to_domain_instancia(f) for f in filas]

    async def saldo_abierto(
        self, producto_id: UUID, sucursal_id: UUID, lote_id: UUID | None = None,
    ) -> Decimal:
        cond = [
            _IA.producto_id == producto_id,
            _IA.sucursal_id == sucursal_id,
            _IA.estado == _ABIERTA,
        ]
        if lote_id is not None:
            cond.append(_IA.lote_id == lote_id)
        total = await self._db.scalar(
            select(func.coalesce(func.sum(_IA.saldo), 0)).where(*cond)
        )
        return Decimal(str(total or 0))
