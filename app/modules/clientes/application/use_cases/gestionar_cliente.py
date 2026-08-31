from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from sqlalchemy.exc import IntegrityError

from app.modules.clientes.domain.entities import Cliente
from app.modules.clientes.domain.exceptions import (
    ClienteNoEncontrado, EmailClienteDuplicado, ClienteConDeuda,
)
from app.modules.clientes.application.ports.cliente_repository import ClienteRepository


async def _cargar(repo: ClienteRepository, cliente_id: UUID) -> Cliente:
    cliente = await repo.obtener_por_id(cliente_id)
    if cliente is None:
        raise ClienteNoEncontrado(f"No existe el cliente con id {cliente_id}")
    return cliente


@dataclass
class ActualizarClienteInput:
    cliente_id: UUID
    nombre: str | None = None
    email: str | None = None
    telefono: str | None = None
    rfc_identificacion: str | None = None
    cambiar_email: bool = False


class ActualizarClienteUseCase:
    """Edita datos de contacto. NO toca el límite de crédito (ver CambiarLimiteCreditoUseCase)."""

    def __init__(self, cliente_repo: ClienteRepository):
        self._repo = cliente_repo

    async def ejecutar(self, data: ActualizarClienteInput) -> Cliente:
        cliente = await _cargar(self._repo, data.cliente_id)

        if data.cambiar_email and data.email:
            otro = await self._repo.buscar_por_email(data.email)
            if otro is not None and otro.id != cliente.id:
                raise EmailClienteDuplicado(
                    f"Ya existe un cliente activo con el email '{data.email}'"
                )

        cliente.actualizar_datos(
            nombre=data.nombre,
            email=data.email,
            telefono=data.telefono,
            rfc_identificacion=data.rfc_identificacion,
            cambiar_email=data.cambiar_email,
        )
        try:
            await self._repo.actualizar(cliente)
        except IntegrityError:
            raise EmailClienteDuplicado(
                f"Ya existe un cliente con el email '{data.email}'"
            )
        return cliente


class DesactivarClienteUseCase:
    def __init__(self, cliente_repo: ClienteRepository):
        self._repo = cliente_repo

    async def ejecutar(self, cliente_id: UUID) -> Cliente:
        cliente = await _cargar(self._repo, cliente_id)
        if cliente.saldo_credito > Decimal("0"):
            raise ClienteConDeuda(
                f"El cliente tiene un saldo de crédito de {cliente.saldo_credito}; "
                "cobrá la deuda antes de desactivarlo."
            )
        cliente.desactivar()
        await self._repo.desactivar(cliente_id)
        return cliente


@dataclass
class AbonarClienteInput:
    cliente_id: UUID
    monto: Decimal


class AbonarClienteUseCase:
    """Registra un pago del cliente contra su saldo de crédito."""

    def __init__(self, cliente_repo: ClienteRepository):
        self._repo = cliente_repo

    async def ejecutar(self, data: AbonarClienteInput) -> Cliente:
        cliente = await _cargar(self._repo, data.cliente_id)
        # Valida (monto > 0 y monto <= saldo) y aplica en memoria; lanza AbonoInvalido.
        cliente.abonar(data.monto)
        await self._repo.decrementar_saldo(data.cliente_id, data.monto)
        return cliente


@dataclass
class CambiarLimiteCreditoInput:
    cliente_id: UUID
    nuevo_limite: Decimal


class CambiarLimiteCreditoUseCase:
    def __init__(self, cliente_repo: ClienteRepository):
        self._repo = cliente_repo

    async def ejecutar(self, data: CambiarLimiteCreditoInput) -> Cliente:
        cliente = await _cargar(self._repo, data.cliente_id)
        # Valida que el nuevo límite no quede por debajo del saldo actual.
        cliente.cambiar_limite_credito(data.nuevo_limite)
        await self._repo.actualizar_limite_credito(data.cliente_id, data.nuevo_limite)
        return cliente
