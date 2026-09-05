from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.inventario.application.ports.lote_repository import LoteRepository
from app.modules.inventario.domain.entities import Lote, ExistenciaLote
from app.modules.inventario.infrastructure.persistence.orm_models import (
    LoteORM, ExistenciaLoteORM,
)
from app.modules.inventario.infrastructure.persistence.mappers import (
    to_domain_lote, to_domain_existencia_lote,
)

_L = LoteORM
_EL = ExistenciaLoteORM

# Orden FEFO: primero el que vence antes; los sin fecha (`NULL`) van al final;
# a igualdad, el más viejo primero.
_FEFO = (_L.fecha_caducidad.asc().nullslast(), _L.created_at.asc())


class SqlAlchemyLoteRepository(LoteRepository):
    def __init__(self, db: AsyncSession):
        self._db = db

    # ------------------------------------------------------------------ lotes
    async def obtener(self, lote_id: UUID) -> Lote | None:
        orm = await self._db.get(_L, lote_id)
        return to_domain_lote(orm) if orm else None

    async def obtener_por_codigo(self, producto_id: UUID, codigo_lote: str) -> Lote | None:
        orm = (await self._db.execute(
            select(_L).where(
                _L.producto_id == producto_id,
                _L.codigo_lote == codigo_lote.strip(),
                _L.activo.is_(True),
            )
        )).scalars().first()
        return to_domain_lote(orm) if orm else None

    async def listar_por_producto(
        self, producto_id: UUID, incluir_inactivos: bool = False
    ) -> list[Lote]:
        stmt = select(_L).where(_L.producto_id == producto_id)
        if not incluir_inactivos:
            stmt = stmt.where(_L.activo.is_(True))
        filas = (await self._db.execute(stmt.order_by(*_FEFO))).scalars().all()
        return [to_domain_lote(f) for f in filas]

    async def por_vencer(
        self, hasta: date, sucursal_ids: list[UUID] | None = None,
        incluir_vencidos: bool = True,
    ) -> list[tuple[Lote, UUID, Decimal]]:
        stmt = (
            select(_L, _EL.sucursal_id, _EL.cantidad)
            .join(_EL, _EL.lote_id == _L.id)
            .where(
                _L.fecha_caducidad.isnot(None),
                _L.fecha_caducidad <= hasta,
                _EL.cantidad > 0,
            )
            .order_by(_L.fecha_caducidad.asc(), _L.created_at.asc())
        )
        if not incluir_vencidos:
            stmt = stmt.where(_L.fecha_caducidad >= date.today())
        if sucursal_ids:
            stmt = stmt.where(_EL.sucursal_id.in_(sucursal_ids))
        filas = (await self._db.execute(stmt)).all()
        return [(to_domain_lote(l), suc, cant) for (l, suc, cant) in filas]

    async def crear(self, lote: Lote) -> None:
        self._db.add(_L(
            id=lote.id,
            producto_id=lote.producto_id,
            codigo_lote=lote.codigo_lote,
            fecha_caducidad=lote.fecha_caducidad,
            costo=lote.costo,
            proveedor=lote.proveedor,
            activo=lote.activo,
        ))
        await self._db.flush()

    async def actualizar(self, lote: Lote) -> None:
        await self._db.execute(
            update(_L).where(_L.id == lote.id).values(
                codigo_lote=lote.codigo_lote,
                fecha_caducidad=lote.fecha_caducidad,
                costo=lote.costo,
                proveedor=lote.proveedor,
                activo=lote.activo,
            )
        )
        await self._db.flush()

    # -------------------------------------------------------- existencia_lote
    async def saldo(self, sucursal_id: UUID, lote_id: UUID) -> Decimal:
        val = await self._db.scalar(
            select(_EL.cantidad).where(
                _EL.sucursal_id == sucursal_id, _EL.lote_id == lote_id
            )
        )
        return val if val is not None else Decimal("0")

    async def lotes_fefo(
        self, producto_id: UUID, sucursal_id: UUID
    ) -> list[tuple[UUID, Decimal]]:
        filas = (await self._db.execute(
            select(_EL.lote_id, _EL.cantidad)
            .join(_L, _L.id == _EL.lote_id)
            .where(
                _EL.producto_id == producto_id,
                _EL.sucursal_id == sucursal_id,
                _EL.cantidad > 0,
                _L.activo.is_(True),
            )
            .order_by(*_FEFO)
        )).all()
        return [(lote_id, cant) for (lote_id, cant) in filas]

    async def ajustar_saldo(
        self, producto_id: UUID, sucursal_id: UUID, lote_id: UUID, delta: Decimal,
    ) -> Decimal:
        fila = (await self._db.execute(
            select(_EL).where(_EL.sucursal_id == sucursal_id, _EL.lote_id == lote_id)
        )).scalars().first()
        if fila is None:
            fila = _EL(
                id=uuid4(),
                producto_id=producto_id,
                sucursal_id=sucursal_id,
                lote_id=lote_id,
                cantidad=delta,
            )
            self._db.add(fila)
            await self._db.flush()
            return fila.cantidad
        fila.cantidad = fila.cantidad + delta
        await self._db.flush()
        return fila.cantidad

    async def listar_saldos(
        self, producto_id: UUID, sucursal_id: UUID | None = None,
        solo_con_saldo: bool = True,
    ) -> list[ExistenciaLote]:
        stmt = (
            select(_EL)
            .join(_L, _L.id == _EL.lote_id)
            .where(_EL.producto_id == producto_id)
            .order_by(*_FEFO)
        )
        if sucursal_id is not None:
            stmt = stmt.where(_EL.sucursal_id == sucursal_id)
        if solo_con_saldo:
            stmt = stmt.where(_EL.cantidad > 0)
        filas = (await self._db.execute(stmt)).scalars().all()
        return [to_domain_existencia_lote(f) for f in filas]
