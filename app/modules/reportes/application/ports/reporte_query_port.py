from abc import ABC, abstractmethod
from uuid import UUID
from dataclasses import dataclass
from decimal import Decimal

@dataclass
class CorteDeCajaOutput:
    caja_turno_id: UUID
    monto_inicial: Decimal
    total_efectivo: Decimal
    total_tarjeta: Decimal
    total_credito: Decimal
    monto_final_esperado: Decimal

class ReporteQueryPort(ABC):
    @abstractmethod
    async def calcular_corte_caja(self, caja_turno_id: UUID) -> CorteDeCajaOutput: ...
