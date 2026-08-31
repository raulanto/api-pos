from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4
from app.modules.clientes.domain.exceptions import (
    LimiteCreditoExcedido, AbonoInvalido, LimiteCreditoInvalido,
)

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

    def abonar(self, monto: Decimal) -> None:
        """Registra un pago del cliente contra su saldo de crédito."""
        if monto <= 0:
            raise AbonoInvalido("El abono debe ser mayor a cero")
        if monto > self.saldo_credito:
            raise AbonoInvalido(
                f"El abono {monto} excede el saldo pendiente {self.saldo_credito}"
            )
        self.saldo_credito -= monto

    def cambiar_limite_credito(self, nuevo_limite: Decimal) -> None:
        if nuevo_limite < 0:
            raise LimiteCreditoInvalido("El límite de crédito no puede ser negativo")
        if nuevo_limite < self.saldo_credito:
            raise LimiteCreditoInvalido(
                f"El nuevo límite {nuevo_limite} es menor que el saldo actual "
                f"{self.saldo_credito}; cobrá al cliente antes de bajarlo"
            )
        self.limite_credito = nuevo_limite

    def actualizar_datos(
        self,
        nombre: str | None = None,
        email: str | None = None,
        telefono: str | None = None,
        rfc_identificacion: str | None = None,
        cambiar_email: bool = False,
    ) -> None:
        if nombre is not None:
            self.nombre = nombre
        if telefono is not None:
            self.telefono = telefono
        if rfc_identificacion is not None:
            self.rfc_identificacion = rfc_identificacion
        # email se limpia/actualiza sólo si se envía explícitamente la clave.
        if cambiar_email:
            self.email = email

    def desactivar(self) -> None:
        self.activo = False
