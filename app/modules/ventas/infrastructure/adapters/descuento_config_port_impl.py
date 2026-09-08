from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ventas.application.ports.descuento_config_port import DescuentoConfigPort
from app.modules.ventas.infrastructure.persistence.orm_models import DescuentoManualLimiteORM


class DescuentoConfigPortImpl(DescuentoConfigPort):
    def __init__(self, db: AsyncSession):
        self._db = db

    async def pct_max_para_rol(self, rol_id: UUID) -> Decimal | None:
        return await self._db.scalar(
            select(DescuentoManualLimiteORM.pct_max).where(
                DescuentoManualLimiteORM.rol_id == rol_id
            )
        )
