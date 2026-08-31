from abc import ABC, abstractmethod
from decimal import Decimal
from uuid import UUID
from app.modules.ventas.domain.entities import CajaTurno

class CajaTurnoRepository(ABC):
    @abstractmethod
    async def obtener_por_id(self, turno_id: UUID) -> CajaTurno | None: ...

    @abstractmethod
    async def guardar(self, turno: CajaTurno) -> None: ...

    @abstractmethod
    async def actualizar(self, turno: CajaTurno) -> None: ...

    @abstractmethod
    async def obtener_abierto_de_usuario(
        self, usuario_id: UUID, sucursal_id: UUID
    ) -> CajaTurno | None: ...

    @abstractmethod
    async def total_efectivo_del_turno(self, turno_id: UUID) -> Decimal:
        """Suma de pagos en efectivo de las ventas no canceladas del turno."""
        ...

    @abstractmethod
    async def contar_ventas_del_turno(self, turno_id: UUID) -> int: ...
