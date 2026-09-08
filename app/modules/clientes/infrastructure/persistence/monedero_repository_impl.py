from uuid import UUID

from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.clientes.application.ports.monedero_repository import MonederoRepository
from app.modules.clientes.domain.entities import MonederoCuenta, MonederoMovimiento
from app.modules.clientes.infrastructure.persistence.orm_models import (
    MonederoCuentaORM, MonederoMovimientoORM,
)
from app.modules.clientes.infrastructure.persistence.mappers import (
    to_domain_monedero_cuenta, to_orm_monedero_cuenta,
    to_domain_monedero_movimiento, to_orm_monedero_movimiento,
)
from app.shared.responses import Page, PageParams, Sort

# Escrituras con `flush`, nunca `commit`: la transacción la cierra get_db().


class SqlAlchemyMonederoRepository(MonederoRepository):
    _ORDEN = {"created_at": MonederoMovimientoORM.created_at}

    def __init__(self, db: AsyncSession):
        self._db = db

    async def obtener_por_telefono(
        self, telefono: str, para_actualizar: bool = False,
    ) -> MonederoCuenta | None:
        stmt = select(MonederoCuentaORM).where(
            MonederoCuentaORM.telefono == telefono.strip()
        )
        if para_actualizar:
            stmt = stmt.with_for_update()
        orm = (await self._db.execute(stmt)).scalar_one_or_none()
        return to_domain_monedero_cuenta(orm) if orm else None

    async def crear_cuenta(self, cuenta: MonederoCuenta) -> None:
        self._db.add(to_orm_monedero_cuenta(cuenta))
        await self._db.flush()

    async def guardar_saldo(self, cuenta: MonederoCuenta) -> None:
        await self._db.execute(
            update(MonederoCuentaORM)
            .where(MonederoCuentaORM.id == cuenta.id)
            .values(saldo=cuenta.saldo)
        )
        await self._db.flush()

    async def registrar_movimiento(self, movimiento: MonederoMovimiento) -> None:
        self._db.add(to_orm_monedero_movimiento(movimiento))
        await self._db.flush()

    async def listar_movimientos(
        self, cuenta_id: UUID, paginacion: PageParams, orden: Sort,
    ) -> Page:
        col = self._ORDEN.get(orden.field, MonederoMovimientoORM.created_at)
        orden_expr = col.desc() if orden.descending else col.asc()
        total = await self._db.scalar(
            select(func.count()).select_from(MonederoMovimientoORM)
            .where(MonederoMovimientoORM.cuenta_id == cuenta_id)
        )
        filas = (await self._db.execute(
            select(MonederoMovimientoORM)
            .where(MonederoMovimientoORM.cuenta_id == cuenta_id)
            .order_by(orden_expr)
            .limit(paginacion.limit)
            .offset(paginacion.offset)
        )).scalars().all()
        return Page(
            items=[to_domain_monedero_movimiento(o) for o in filas],
            total=int(total or 0),
        )

    async def movimientos_de_venta(self, venta_id: UUID) -> list[MonederoMovimiento]:
        filas = (await self._db.execute(
            select(MonederoMovimientoORM)
            .where(MonederoMovimientoORM.venta_id == venta_id)
            .order_by(MonederoMovimientoORM.created_at.asc())
        )).scalars().all()
        return [to_domain_monedero_movimiento(o) for o in filas]
