from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4
from app.modules.clientes.domain.exceptions import (
    LimiteCreditoExcedido, AbonoInvalido, LimiteCreditoInvalido,
    SaldoMonederoInsuficiente, MovimientoMonederoInvalido,
)
from app.modules.clientes.domain.value_objects import TipoMovimientoMonedero


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

    # Relación embebida opcional (`?include=sucursal`); la puebla el mapper.
    sucursal: object | None = field(default=None, compare=False, repr=False)

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


# --------------------------------------------------------------------------- #
# Monedero electrónico (cashback por teléfono)
# --------------------------------------------------------------------------- #
@dataclass
class MonederoCuenta:
    """Saldo de monedero de un teléfono. Independiente de `Cliente`: no exige
    dar de alta cliente ni tiene sucursal (el saldo sirve en cualquiera)."""
    id: UUID
    telefono: str
    saldo: Decimal
    activo: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @staticmethod
    def crear(telefono: str) -> "MonederoCuenta":
        tel = (telefono or "").strip()
        if not tel:
            raise MovimientoMonederoInvalido("El teléfono del monedero es obligatorio.")
        return MonederoCuenta(id=uuid4(), telefono=tel, saldo=Decimal("0"), activo=True)

    def acreditar(self, monto: Decimal) -> None:
        if monto <= 0:
            raise MovimientoMonederoInvalido("El monto a acreditar debe ser mayor a cero.")
        self.saldo += monto

    def debitar(self, monto: Decimal) -> None:
        if monto <= 0:
            raise MovimientoMonederoInvalido("El monto a debitar debe ser mayor a cero.")
        if monto > self.saldo:
            raise SaldoMonederoInsuficiente(
                f"El monedero tiene {self.saldo} y se intentó usar {monto}."
            )
        self.saldo -= monto

    def debitar_hasta(self, monto: Decimal) -> Decimal:
        """Debita `min(monto, saldo)`. Devuelve lo efectivamente debitado. Para
        revertir una acumulación cuando el saldo ya se gastó en parte."""
        quita = min(monto, self.saldo) if monto > 0 else Decimal("0")
        self.saldo -= quita
        return quita

    def ajustar(self, monto: Decimal) -> None:
        """Ajuste manual (+/-). Nunca deja el saldo negativo."""
        if monto == 0:
            raise MovimientoMonederoInvalido("El ajuste no puede ser cero.")
        nuevo = self.saldo + monto
        if nuevo < 0:
            raise SaldoMonederoInsuficiente(
                f"El ajuste {monto} dejaría el saldo en {nuevo}."
            )
        self.saldo = nuevo


@dataclass
class MonederoMovimiento:
    """Una línea del ledger. Es el historial del monedero."""
    id: UUID
    cuenta_id: UUID
    tipo: TipoMovimientoMonedero
    monto: Decimal                      # siempre positivo; el signo lo da `tipo`
    saldo_resultante: Decimal
    venta_id: UUID | None = None
    usuario_id: UUID | None = None
    motivo: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @staticmethod
    def crear(cuenta_id: UUID, tipo: TipoMovimientoMonedero, monto: Decimal,
              saldo_resultante: Decimal, venta_id: UUID | None = None,
              usuario_id: UUID | None = None, motivo: str | None = None) -> "MonederoMovimiento":
        return MonederoMovimiento(
            id=uuid4(), cuenta_id=cuenta_id, tipo=tipo, monto=abs(monto),
            saldo_resultante=saldo_resultante, venta_id=venta_id,
            usuario_id=usuario_id, motivo=motivo,
        )
