from uuid import UUID
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func
from app.modules.clientes.application.ports.cliente_repository import ClienteRepository
from app.modules.clientes.domain.entities import Cliente
from app.modules.clientes.infrastructure.persistence.orm_models import ClienteORM
from app.modules.clientes.infrastructure.persistence.mappers import to_domain_cliente, to_orm_cliente

class SqlAlchemyClienteRepository(ClienteRepository):
    def __init__(self, db: AsyncSession):
        self._db = db

    async def guardar(self, cliente: Cliente) -> None:
        orm = to_orm_cliente(cliente)
        await self._db.merge(orm)
        await self._db.flush()

    async def obtener_por_id(self, cliente_id: UUID) -> Cliente | None:
        stmt = select(ClienteORM).where(ClienteORM.id == cliente_id)
        result = await self._db.execute(stmt)
        orm = result.scalar_one_or_none()
        return to_domain_cliente(orm) if orm else None

    async def incrementar_saldo(self, cliente_id: UUID, monto: Decimal) -> None:
        # Atomic update of saldo_credito
        stmt = (
            update(ClienteORM)
            .where(ClienteORM.id == cliente_id)
            .values(saldo_credito=ClienteORM.saldo_credito + monto)
        )
        await self._db.execute(stmt)
        await self._db.flush()

    async def decrementar_saldo(self, cliente_id: UUID, monto: Decimal) -> None:
        # Atomic; nunca deja el saldo por debajo de 0 (p. ej. al anular una venta).
        stmt = (
            update(ClienteORM)
            .where(ClienteORM.id == cliente_id)
            .values(saldo_credito=func.greatest(ClienteORM.saldo_credito - monto, 0))
        )
        await self._db.execute(stmt)
        await self._db.flush()
