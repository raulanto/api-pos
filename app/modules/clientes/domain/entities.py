from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4
from app.modules.clientes.domain.exceptions import LimiteCreditoExcedido

@dataclass
class Cliente:
    id: UUID
    sucursal_id: UUID
    nombre: str
    email: str | None
    telefono: str | None
    rfc_identificacion: str | None
    limite_credito: Decimal
    saldo_credito: Decimal
    activo: bool
    created_at: datetime = field(default_factory=datetime.utcnow)

    @staticmethod
    def crear(
        sucursal_id: UUID, nombre: str,
        email: str | None = None, telefono: str | None = None,
        rfc_identificacion: str | None = None,
        limite_credito: Decimal = Decimal("0")
    ) -> "Cliente":
        return Cliente(
            id=uuid4(),
            sucursal_id=sucursal_id,
            nombre=nombre,
            email=email,
            telefono=telefono,
            rfc_identificacion=rfc_identificacion,
            limite_credito=limite_credito,
            saldo_credito=Decimal("0"),
            activo=True
        )

    def incrementar_saldo(self, monto: Decimal) -> None:
        if monto <= 0:
            raise ValueError("El monto a incrementar debe ser mayor a cero")
            
        disponible = self.limite_credito - self.saldo_credito
        if monto > disponible:
            raise LimiteCreditoExcedido(f"Saldo pendiente {monto} excede crédito disponible {disponible}")
            
        self.saldo_credito += monto
