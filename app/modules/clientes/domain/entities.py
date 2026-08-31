from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4
from app.modules.clientes.domain.exceptions import (
    LimiteCreditoExcedido, AbonoInvalido, LimiteCreditoInvalido,
)


"""
    Cliente
    Descripcion: Clase que representa un cliente.
    Atributos:
    - id: ID del cliente.
    - sucursal_id: ID de la sucursal.
    - nombre: Nombre del cliente.
    - email: Email del cliente.
    - telefono: Telefono del cliente.
    - rfc_identificacion: RFC o identificación del cliente.
    - limite_credito: Límite de crédito del cliente.
    - saldo_credito: Saldo de crédito del cliente.
    - activo: Indica si el cliente está activo.
    - created_at: Fecha de creación del cliente.
    Métodos:
    - crear: Crea un nuevo cliente.
    - incrementar_saldo: Incrementa el saldo de crédito del cliente.
    - abonar: Abona al saldo de crédito del cliente.
    - cambiar_limite_credito: Cambia el límite de crédito del cliente.
    - actualizar_datos: Actualiza los datos del cliente.
    - desactivar: Desactiva el cliente.
"""
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

    """
        Método para crear un nuevo cliente.
        Parámetros:
        - sucursal_id: ID de la sucursal.
        - nombre: Nombre del cliente.
        - email: Email del cliente.
        - telefono: Telefono del cliente.
        - rfc_identificacion: RFC o identificación del cliente.
        - limite_credito: Límite de crédito del cliente.
        Retorna:
        - Cliente: Cliente creado.
    """
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
    """
        Método para incrementar el saldo de crédito del cliente.
        Parámetros:
        - monto: Monto a incrementar.
        Retorna:
        - None
    """
    def incrementar_saldo(self, monto: Decimal) -> None:
        if monto <= 0:
            raise ValueError("El monto a incrementar debe ser mayor a cero")

        disponible = self.limite_credito - self.saldo_credito
        if monto > disponible:
            raise LimiteCreditoExcedido(f"Saldo pendiente {monto} excede crédito disponible {disponible}")

        self.saldo_credito += monto
    """
        Método para abonar al saldo de crédito del cliente.
        Parámetros:
        - monto: Monto a abonar.
        Retorna:
        - None
    """
    def abonar(self, monto: Decimal) -> None:
        """Registra un pago del cliente contra su saldo de crédito."""
        if monto <= 0:
            raise AbonoInvalido("El abono debe ser mayor a cero")
        if monto > self.saldo_credito:
            raise AbonoInvalido(
                f"El abono {monto} excede el saldo pendiente {self.saldo_credito}"
            )
        self.saldo_credito -= monto
    """
        Método para cambiar el límite de crédito del cliente.
        Parámetros:
        - nuevo_limite: Nuevo límite de crédito.
        Retorna:
        - None
    """
    def cambiar_limite_credito(self, nuevo_limite: Decimal) -> None:
        if nuevo_limite < 0:
            raise LimiteCreditoInvalido("El límite de crédito no puede ser negativo")
        if nuevo_limite < self.saldo_credito:
            raise LimiteCreditoInvalido(
                f"El nuevo límite {nuevo_limite} es menor que el saldo actual "
                f"{self.saldo_credito}; cobrá al cliente antes de bajarlo"
            )
        self.limite_credito = nuevo_limite
    """
        Método para actualizar los datos del cliente.
        Parámetros:
        - nombre: Nombre del cliente.
        - email: Email del cliente.
        - telefono: Telefono del cliente.
        - rfc_identificacion: RFC o identificación del cliente.
        - cambiar_email: Indica si se debe cambiar el email.
        Retorna:
        - None
    """
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
