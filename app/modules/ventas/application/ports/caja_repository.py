from abc import ABC, abstractmethod
from uuid import UUID
from app.modules.ventas.domain.entities import CajaTurno

class CajaTurnoRepository(ABC):
    @abstractmethod
    async def obtener_por_id(self, turno_id: UUID) -> CajaTurno | None: ...
