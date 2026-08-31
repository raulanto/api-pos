from decimal import Decimal
from uuid import UUID

from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.ventas.application.ports.venta_repository import VentaRepository
from app.modules.ventas.application.ports.caja_repository import CajaTurnoRepository
from app.modules.ventas.application.dtos import FiltroVentas, Paginacion, Pagina
from app.modules.ventas.domain.entities import Venta, CajaTurno, ESTADO_TURNO_ABIERTO
from app.modules.ventas.domain.value_objects import EstadoVenta, MetodoPago
from app.modules.ventas.infrastructure.persistence.orm_models import (
    VentaORM, CajaTurnoORM, PagoORM,
)
from app.modules.ventas.infrastructure.persistence.mappers import (
    to_domain_venta, to_orm_venta, to_domain_caja_turno, to_orm_caja_turno,
)

# Los métodos de escritura hacen `flush`, nunca `commit`: la transacción la
# cierra `get_db()` (una por request).


class SqlAlchemyVentaRepository(VentaRepository):
    def __init__(self, db: AsyncSession):
        self._db = db

    async def guardar(self, venta: Venta) -> None:
        self._db.add(to_orm_venta(venta))
        await self._db.flush()

    async def obtener_por_id(self, venta_id: UUID) -> Venta | None:
        stmt = (
            select(VentaORM)
            .options(selectinload(VentaORM.lineas), selectinload(VentaORM.pagos))
            .where(VentaORM.id == venta_id)
        )
        orm = (await self._db.execute(stmt)).scalar_one_or_none()
        return to_domain_venta(orm) if orm else None

    async def obtener_por_idempotency_key(self, key: str) -> Venta | None:
        stmt = (
            select(VentaORM)
            .options(selectinload(VentaORM.lineas), selectinload(VentaORM.pagos))
            .where(VentaORM.idempotency_key == key)
        )
        orm = (await self._db.execute(stmt)).scalar_one_or_none()
        return to_domain_venta(orm) if orm else None

    async def actualizar_estado(self, venta_id: UUID, estado: EstadoVenta) -> None:
        await self._db.execute(
            update(VentaORM).where(VentaORM.id == venta_id).values(estado=estado.value)
        )
        await self._db.flush()

    async def listar(self, filtro: FiltroVentas, paginacion: Paginacion) -> Pagina:
        condiciones = []
        if filtro.sucursal_id is not None:
            condiciones.append(VentaORM.sucursal_id == filtro.sucursal_id)
        if filtro.caja_turno_id is not None:
            condiciones.append(VentaORM.caja_turno_id == filtro.caja_turno_id)
        if filtro.cliente_id is not None:
            condiciones.append(VentaORM.cliente_id == filtro.cliente_id)
        if filtro.estado is not None:
            condiciones.append(VentaORM.estado == filtro.estado.value)
        if filtro.desde is not None:
            condiciones.append(VentaORM.created_at >= filtro.desde)
        if filtro.hasta is not None:
            condiciones.append(VentaORM.created_at <= filtro.hasta)

        total = await self._db.scalar(
            select(func.count()).select_from(VentaORM).where(*condiciones)
        )
        filas = (await self._db.execute(
            select(VentaORM)
            .options(selectinload(VentaORM.lineas), selectinload(VentaORM.pagos))
            .where(*condiciones)
            .order_by(VentaORM.created_at.desc())
            .limit(paginacion.limit)
            .offset(paginacion.offset)
        )).scalars().all()
        return Pagina(items=[to_domain_venta(o) for o in filas], total=int(total or 0))


class SqlAlchemyCajaTurnoRepository(CajaTurnoRepository):
    def __init__(self, db: AsyncSession):
        self._db = db

    async def obtener_por_id(self, turno_id: UUID) -> CajaTurno | None:
        orm = (await self._db.execute(
            select(CajaTurnoORM).where(CajaTurnoORM.id == turno_id)
        )).scalar_one_or_none()
        return to_domain_caja_turno(orm) if orm else None

    async def guardar(self, turno: CajaTurno) -> None:
        self._db.add(to_orm_caja_turno(turno))
        await self._db.flush()

    async def actualizar(self, turno: CajaTurno) -> None:
        await self._db.execute(
            update(CajaTurnoORM)
            .where(CajaTurnoORM.id == turno.id)
            .values(
                estado=turno.estado,
                cerrado_en=turno.cerrado_en,
                saldo_final_declarado=turno.saldo_final_declarado,
                diferencia=turno.diferencia,
            )
        )
        await self._db.flush()

    async def obtener_abierto_de_usuario(
        self, usuario_id: UUID, sucursal_id: UUID
    ) -> CajaTurno | None:
        orm = (await self._db.execute(
            select(CajaTurnoORM)
            .where(
                CajaTurnoORM.usuario_id == usuario_id,
                CajaTurnoORM.sucursal_id == sucursal_id,
                CajaTurnoORM.estado == ESTADO_TURNO_ABIERTO,
            )
            .order_by(CajaTurnoORM.abierto_en.desc())
        )).scalars().first()
        return to_domain_caja_turno(orm) if orm else None

    async def total_efectivo_del_turno(self, turno_id: UUID) -> Decimal:
        total = await self._db.scalar(
            select(func.coalesce(func.sum(PagoORM.monto), 0))
            .select_from(PagoORM)
            .join(VentaORM, VentaORM.id == PagoORM.venta_id)
            .where(
                VentaORM.caja_turno_id == turno_id,
                VentaORM.estado != EstadoVenta.CANCELADA.value,
                PagoORM.metodo_pago == MetodoPago.EFECTIVO.value,
            )
        )
        return Decimal(total or 0)

    async def contar_ventas_del_turno(self, turno_id: UUID) -> int:
        total = await self._db.scalar(
            select(func.count())
            .select_from(VentaORM)
            .where(
                VentaORM.caja_turno_id == turno_id,
                VentaORM.estado != EstadoVenta.CANCELADA.value,
            )
        )
        return int(total or 0)
