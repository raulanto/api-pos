from decimal import Decimal
from uuid import UUID

from sqlalchemy import select, update, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.clientes.application.ports.cliente_repository import ClienteRepository
from app.modules.clientes.application.dtos import FiltroClientes
from app.modules.clientes.domain.entities import Cliente
from app.modules.clientes.infrastructure.persistence.orm_models import ClienteORM
from app.modules.clientes.infrastructure.persistence.mappers import to_domain_cliente, to_orm_cliente
from app.shared.responses import Page, PageParams, Sort

# Escrituras con `flush`, nunca `commit`: la transacción la cierra get_db().


class SqlAlchemyClienteRepository(ClienteRepository):
    # Mapa nombre lógico (whitelist del router) -> columna ORM.
    _ORDEN = {
        "created_at": ClienteORM.created_at,
        "nombre": ClienteORM.nombre,
        "saldo_credito": ClienteORM.saldo_credito,
    }

    def __init__(self, db: AsyncSession):
        self._db = db

    async def guardar(self, cliente: Cliente) -> None:
        await self._db.merge(to_orm_cliente(cliente))
        await self._db.flush()

    async def actualizar(self, cliente: Cliente) -> None:
        await self._db.execute(
            update(ClienteORM)
            .where(ClienteORM.id == cliente.id)
            .values(
                nombre=cliente.nombre,
                email=cliente.email,
                telefono=cliente.telefono,
                rfc_identificacion=cliente.rfc_identificacion,
                activo=cliente.activo,
            )
        )
        await self._db.flush()

    async def obtener_por_id(self, cliente_id: UUID) -> Cliente | None:
        orm = (await self._db.execute(
            select(ClienteORM).where(ClienteORM.id == cliente_id)
        )).scalar_one_or_none()
        return to_domain_cliente(orm) if orm else None

    async def buscar_por_email(self, email: str, solo_activos: bool = True) -> Cliente | None:
        stmt = select(ClienteORM).where(func.lower(ClienteORM.email) == email.strip().lower())
        if solo_activos:
            stmt = stmt.where(ClienteORM.activo.is_(True))
        orm = (await self._db.execute(stmt)).scalars().first()
        return to_domain_cliente(orm) if orm else None

    async def listar(
        self, filtro: FiltroClientes, paginacion: PageParams, orden: Sort
    ) -> Page:
        condiciones = []
        if filtro.sucursal_id is not None:
            condiciones.append(ClienteORM.sucursal_id == filtro.sucursal_id)
        if filtro.activo is not None:
            condiciones.append(ClienteORM.activo == filtro.activo)
        if filtro.con_saldo_pendiente:
            condiciones.append(ClienteORM.saldo_credito > 0)
        if filtro.busqueda:
            patron = f"%{filtro.busqueda.strip()}%"
            condiciones.append(or_(
                ClienteORM.nombre.ilike(patron),
                ClienteORM.email.ilike(patron),
            ))

        col = self._ORDEN.get(orden.field, ClienteORM.nombre)
        orden_expr = col.desc() if orden.descending else col.asc()

        total = await self._db.scalar(
            select(func.count()).select_from(ClienteORM).where(*condiciones)
        )
        filas = (await self._db.execute(
            select(ClienteORM)
            .where(*condiciones)
            .order_by(orden_expr)
            .limit(paginacion.limit)
            .offset(paginacion.offset)
        )).scalars().all()
        return Page(items=[to_domain_cliente(o) for o in filas], total=int(total or 0))

    async def incrementar_saldo(self, cliente_id: UUID, monto: Decimal) -> None:
        await self._db.execute(
            update(ClienteORM)
            .where(ClienteORM.id == cliente_id)
            .values(saldo_credito=ClienteORM.saldo_credito + monto)
        )
        await self._db.flush()

    async def decrementar_saldo(self, cliente_id: UUID, monto: Decimal) -> None:
        # Atómico; nunca deja el saldo por debajo de 0 (abono o anulación de venta).
        await self._db.execute(
            update(ClienteORM)
            .where(ClienteORM.id == cliente_id)
            .values(saldo_credito=func.greatest(ClienteORM.saldo_credito - monto, 0))
        )
        await self._db.flush()

    async def actualizar_limite_credito(self, cliente_id: UUID, nuevo_limite: Decimal) -> None:
        await self._db.execute(
            update(ClienteORM)
            .where(ClienteORM.id == cliente_id)
            .values(limite_credito=nuevo_limite)
        )
        await self._db.flush()

    async def desactivar(self, cliente_id: UUID) -> None:
        await self._db.execute(
            update(ClienteORM).where(ClienteORM.id == cliente_id).values(activo=False)
        )
        await self._db.flush()
