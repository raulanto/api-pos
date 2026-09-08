from decimal import Decimal
from uuid import UUID

from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.ventas.application.ports.venta_repository import VentaRepository
from app.modules.ventas.application.ports.caja_repository import (
    CajaRepository, CajaTurnoRepository,
)
from app.modules.ventas.application.ports.devolucion_repository import DevolucionRepository
from app.modules.ventas.application.dtos import FiltroVentas, FiltroTurnos
from app.shared.responses import Page, PageParams, Sort
from app.modules.ventas.domain.entities import (
    Venta, Caja, CajaTurno, CajaMovimiento, DenominacionConteo, Devolucion,
    ESTADO_TURNO_ABIERTO,
)
from app.modules.ventas.domain.value_objects import EstadoVenta, MetodoPago
from app.modules.ventas.infrastructure.persistence.orm_models import (
    VentaORM, CajaORM, CajaTurnoORM, CajaMovimientoORM, CajaDenominacionORM,
    PagoORM, DetalleVentaORM, DevolucionORM,
)
from app.modules.ventas.infrastructure.persistence.mappers import (
    to_domain_venta, to_orm_venta, to_domain_caja, to_orm_caja,
    to_domain_caja_turno, to_orm_caja_turno, to_domain_movimiento_caja,
    to_orm_movimiento_caja, to_orm_denominacion, to_domain_denominacion,
    to_orm_devolucion, to_domain_devolucion,
)

# Los métodos de escritura hacen `flush`, nunca `commit`: la transacción la
# cierra `get_db()` (una por request).


class SqlAlchemyVentaRepository(VentaRepository):
    _ORDEN = {
        "created_at": VentaORM.created_at,
    }
    _INCLUDES = {
        "cliente": VentaORM.cliente,
        "usuario": VentaORM.usuario,
        "caja_turno": VentaORM.caja_turno,
    }

    def __init__(self, db: AsyncSession):
        self._db = db

    def _opts(self, includes: frozenset[str]):
        opts = [selectinload(VentaORM.lineas), selectinload(VentaORM.pagos)]
        opts += [selectinload(self._INCLUDES[i]) for i in includes if i in self._INCLUDES]
        return opts

    async def guardar(self, venta: Venta) -> None:
        self._db.add(to_orm_venta(venta))
        await self._db.flush()

    async def obtener_por_id(
        self, venta_id: UUID, includes: frozenset[str] = frozenset()
    ) -> Venta | None:
        stmt = (
            select(VentaORM)
            .options(*self._opts(includes))
            .where(VentaORM.id == venta_id)
        )
        orm = (await self._db.execute(stmt)).scalar_one_or_none()
        return to_domain_venta(orm, includes) if orm else None

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

    async def registrar_monedero_generado(self, venta_id: UUID, monto) -> None:
        await self._db.execute(
            update(VentaORM).where(VentaORM.id == venta_id).values(monedero_generado=monto)
        )
        await self._db.flush()

    async def registrar_devolucion(self, venta: Venta) -> None:
        await self._db.execute(
            update(VentaORM).where(VentaORM.id == venta.id).values(estado=venta.estado.value)
        )
        for linea in venta.lineas:
            await self._db.execute(
                update(DetalleVentaORM)
                .where(DetalleVentaORM.id == linea.id)
                .values(cantidad_devuelta=linea.cantidad_devuelta)
            )
        await self._db.flush()

    async def listar(
        self,
        filtro: FiltroVentas,
        paginacion: PageParams,
        orden: Sort,
        includes: frozenset[str] = frozenset(),
    ) -> Page:
        condiciones = []
        if filtro.sucursal_id is not None:
            condiciones.append(VentaORM.sucursal_id == filtro.sucursal_id)
        if filtro.caja_turno_id is not None:
            condiciones.append(VentaORM.caja_turno_id == filtro.caja_turno_id)
        if filtro.cliente_id is not None:
            condiciones.append(VentaORM.cliente_id == filtro.cliente_id)
        if filtro.telefono is not None:
            condiciones.append(VentaORM.telefono == filtro.telefono.strip())
        if filtro.estado is not None:
            condiciones.append(VentaORM.estado == filtro.estado.value)
        if filtro.desde is not None:
            condiciones.append(VentaORM.created_at >= filtro.desde)
        if filtro.hasta is not None:
            condiciones.append(VentaORM.created_at <= filtro.hasta)

        col = self._ORDEN.get(orden.field, VentaORM.created_at)
        orden_expr = col.desc() if orden.descending else col.asc()

        total = await self._db.scalar(
            select(func.count()).select_from(VentaORM).where(*condiciones)
        )
        filas = (await self._db.execute(
            select(VentaORM)
            .options(*self._opts(includes))
            .where(*condiciones)
            .order_by(orden_expr)
            .limit(paginacion.limit)
            .offset(paginacion.offset)
        )).scalars().all()
        return Page(
            items=[to_domain_venta(o, includes) for o in filas], total=int(total or 0)
        )


class SqlAlchemyDevolucionRepository(DevolucionRepository):
    def __init__(self, db: AsyncSession):
        self._db = db

    async def crear(self, devolucion: Devolucion) -> None:
        self._db.add(to_orm_devolucion(devolucion))
        await self._db.flush()

    async def obtener_por_idempotency_key(self, key: str) -> Devolucion | None:
        orm = (await self._db.execute(
            select(DevolucionORM)
            .options(selectinload(DevolucionORM.lineas))
            .where(DevolucionORM.idempotency_key == key)
        )).scalar_one_or_none()
        return to_domain_devolucion(orm) if orm else None

    async def listar_por_venta(self, venta_id: UUID) -> list[Devolucion]:
        filas = (await self._db.execute(
            select(DevolucionORM)
            .options(selectinload(DevolucionORM.lineas))
            .where(DevolucionORM.venta_id == venta_id)
            .order_by(DevolucionORM.created_at.asc())
        )).scalars().all()
        return [to_domain_devolucion(o) for o in filas]


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
                nota_cierre=turno.nota_cierre,
                conciliado_por=turno.conciliado_por,
                conciliado_en=turno.conciliado_en,
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

    async def total_devoluciones_efectivo_del_turno(self, turno_id: UUID) -> Decimal:
        total = await self._db.scalar(
            select(func.coalesce(func.sum(DevolucionORM.monto_devuelto), 0))
            .where(
                DevolucionORM.caja_turno_id == turno_id,
                DevolucionORM.metodo_devolucion == "efectivo",
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

    # --- Movimientos de caja ---
    async def registrar_movimiento(self, mov: CajaMovimiento) -> None:
        self._db.add(to_orm_movimiento_caja(mov))
        await self._db.flush()

    async def listar_movimientos(self, turno_id: UUID) -> list[CajaMovimiento]:
        filas = (await self._db.execute(
            select(CajaMovimientoORM)
            .where(CajaMovimientoORM.caja_turno_id == turno_id)
            .order_by(CajaMovimientoORM.created_at.asc())
        )).scalars().all()
        return [to_domain_movimiento_caja(o) for o in filas]

    async def movimientos_por_tipo(self, turno_id: UUID) -> dict[str, Decimal]:
        filas = (await self._db.execute(
            select(CajaMovimientoORM.tipo, func.coalesce(func.sum(CajaMovimientoORM.monto), 0))
            .where(CajaMovimientoORM.caja_turno_id == turno_id)
            .group_by(CajaMovimientoORM.tipo)
        )).all()
        return {tipo: Decimal(total) for tipo, total in filas}

    async def movimientos_neto_del_turno(self, turno_id: UUID) -> Decimal:
        por_tipo = await self.movimientos_por_tipo(turno_id)
        return (
            por_tipo.get("ingreso", Decimal("0"))
            - por_tipo.get("retiro", Decimal("0"))
            - por_tipo.get("gasto", Decimal("0"))
        )

    # --- Desglose por denominación ---
    async def guardar_denominaciones(
        self, turno_id: UUID, momento: str, conteos: list[DenominacionConteo]
    ) -> None:
        for c in conteos:
            self._db.add(to_orm_denominacion(turno_id, momento, c))
        await self._db.flush()

    async def listar_denominaciones(
        self, turno_id: UUID, momento: str | None = None
    ) -> list[DenominacionConteo]:
        cond = [CajaDenominacionORM.caja_turno_id == turno_id]
        if momento is not None:
            cond.append(CajaDenominacionORM.momento == momento)
        filas = (await self._db.execute(
            select(CajaDenominacionORM).where(*cond)
            .order_by(CajaDenominacionORM.valor.desc())
        )).scalars().all()
        return [to_domain_denominacion(o) for o in filas]

    # --- Histórico / dashboard ---
    async def listar_turnos(
        self, filtro: FiltroTurnos, paginacion: PageParams, orden: Sort
    ) -> Page:
        cond = []
        if filtro.sucursal_id is not None:
            cond.append(CajaTurnoORM.sucursal_id == filtro.sucursal_id)
        if filtro.caja_id is not None:
            cond.append(CajaTurnoORM.caja_id == filtro.caja_id)
        if filtro.usuario_id is not None:
            cond.append(CajaTurnoORM.usuario_id == filtro.usuario_id)
        if filtro.estado is not None:
            cond.append(CajaTurnoORM.estado == filtro.estado)
        if filtro.desde is not None:
            cond.append(CajaTurnoORM.abierto_en >= filtro.desde)
        if filtro.hasta is not None:
            cond.append(CajaTurnoORM.abierto_en <= filtro.hasta)

        col = {"abierto_en": CajaTurnoORM.abierto_en, "cerrado_en": CajaTurnoORM.cerrado_en}.get(
            orden.field, CajaTurnoORM.abierto_en
        )
        orden_expr = col.desc() if orden.descending else col.asc()

        total = await self._db.scalar(
            select(func.count()).select_from(CajaTurnoORM).where(*cond)
        )
        filas = (await self._db.execute(
            select(CajaTurnoORM).where(*cond)
            .order_by(orden_expr)
            .limit(paginacion.limit).offset(paginacion.offset)
        )).scalars().all()
        return Page(
            items=[to_domain_caja_turno(o) for o in filas], total=int(total or 0),
        )

    async def efectivo_en_sucursal(self, sucursal_id: UUID) -> Decimal:
        turnos = (await self._db.execute(
            select(CajaTurnoORM.id, CajaTurnoORM.saldo_inicial)
            .where(
                CajaTurnoORM.sucursal_id == sucursal_id,
                CajaTurnoORM.estado == ESTADO_TURNO_ABIERTO,
            )
        )).all()
        total = Decimal("0")
        for turno_id, saldo_inicial in turnos:
            efectivo = await self.total_efectivo_del_turno(turno_id)
            dev = await self.total_devoluciones_efectivo_del_turno(turno_id)
            neto = await self.movimientos_neto_del_turno(turno_id)
            total += Decimal(saldo_inicial) + efectivo - dev + neto
        return total


class SqlAlchemyCajaRepository(CajaRepository):
    def __init__(self, db: AsyncSession):
        self._db = db

    async def obtener_por_id(self, caja_id: UUID) -> Caja | None:
        orm = (await self._db.execute(
            select(CajaORM).where(CajaORM.id == caja_id)
        )).scalar_one_or_none()
        return to_domain_caja(orm) if orm else None

    async def listar(
        self, sucursal_id: UUID, incluir_inactivas: bool = False
    ) -> list[Caja]:
        cond = [CajaORM.sucursal_id == sucursal_id]
        if not incluir_inactivas:
            cond.append(CajaORM.activa.is_(True))
        filas = (await self._db.execute(
            select(CajaORM).where(*cond).order_by(CajaORM.nombre.asc())
        )).scalars().all()
        return [to_domain_caja(o) for o in filas]

    async def guardar(self, caja: Caja) -> None:
        self._db.add(to_orm_caja(caja))
        await self._db.flush()

    async def actualizar(self, caja: Caja) -> None:
        await self._db.execute(
            update(CajaORM).where(CajaORM.id == caja.id)
            .values(nombre=caja.nombre, activa=caja.activa)
        )
        await self._db.flush()

    async def nombre_en_uso(
        self, sucursal_id: UUID, nombre: str, excluir_id: UUID | None = None
    ) -> bool:
        cond = [
            CajaORM.sucursal_id == sucursal_id,
            func.lower(CajaORM.nombre) == nombre.strip().lower(),
            CajaORM.activa.is_(True),
        ]
        if excluir_id is not None:
            cond.append(CajaORM.id != excluir_id)
        return (await self._db.scalar(
            select(func.count()).select_from(CajaORM).where(*cond)
        )) > 0
