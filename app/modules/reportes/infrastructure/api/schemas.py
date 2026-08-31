from pydantic import BaseModel
from uuid import UUID
from decimal import Decimal

class CorteDeCajaResponse(BaseModel):
    caja_turno_id: UUID
    monto_inicial: Decimal
    total_efectivo: Decimal
    total_tarjeta: Decimal
    total_credito: Decimal
    monto_final_esperado: Decimal
