from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from sqlalchemy.exc import IntegrityError

from app.modules.clientes.domain.entities import Cliente
from app.modules.clientes.domain.exceptions import (
    ClienteNoEncontrado, EmailClienteDuplicado, ClienteConDeuda,
)
from app.modules.clientes.application.ports.cliente_repository import ClienteRepository

"""
    _cargar
    Descripcion: Método privado para cargar un cliente por ID.
    Parámetros:
    - repo: Repositorio de clientes.
    - cliente_id: ID del cliente.
    Retorna:
    - Cliente: Cliente encontrado.
"""
async def _cargar(repo: ClienteRepository, cliente_id: UUID) -> Cliente:
    cliente = await repo.obtener_por_id(cliente_id)
    if cliente is None:
        raise ClienteNoEncontrado(f"No existe el cliente con id {cliente_id}")
    return cliente


"""
    ActualizarClienteInput
    Descripcion: Clase que representa los datos de entrada para actualizar un cliente.
    Atributos:
    - cliente_id: ID del cliente.
    - nombre: Nombre del cliente.
    - email: Email del cliente.
    - telefono: Telefono del cliente.
    - rfc_identificacion: RFC del cliente.
    - cambiar_email: Indica si se debe cambiar el email.
"""
@dataclass
class ActualizarClienteInput:
    cliente_id: UUID
    nombre: str | None = None
    email: str | None = None
    telefono: str | None = None
    rfc_identificacion: str | None = None
    cambiar_email: bool = False


"""
    ActualizarClienteUseCase
    Descripcion: Clase que representa el caso de uso para actualizar un cliente.
    Métodos:
    - ejecutar: Ejecuta el caso de uso para actualizar un cliente.
"""
class ActualizarClienteUseCase:
    """Edita datos de contacto. NO toca el límite de crédito (ver CambiarLimiteCreditoUseCase)."""

    def __init__(self, cliente_repo: ClienteRepository):
        self._repo = cliente_repo

    """
        Método para ejecutar el caso de uso para actualizar un cliente.
        Parámetros:
        - data: Datos de entrada para actualizar un cliente.
        Retorna:
        - Cliente: Cliente actualizado.
    """
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

"""
    DesactivarClienteUseCase
    Descripcion: Clase que representa el caso de uso para desactivar un cliente.
    Métodos:
    - ejecutar: Ejecuta el caso de uso para desactivar un cliente.
"""
class DesactivarClienteUseCase:
    def __init__(self, cliente_repo: ClienteRepository):
        self._repo = cliente_repo

    """
        Método para ejecutar el caso de uso para desactivar un cliente.
        Parámetros:
        - cliente_id: ID del cliente.
        Retorna:
        - Cliente: Cliente desactivado.
    """
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

"""
    AbonarClienteInput
    Descripcion: Clase que representa los datos de entrada para abonar un pago a un cliente.
    Atributos:
    - cliente_id: ID del cliente.
    - monto: Monto del pago.
"""
@dataclass
class AbonarClienteInput:
    cliente_id: UUID
    monto: Decimal

"""
    AbonarClienteUseCase
    Descripcion: Clase que representa el caso de uso para abonar un pago a un cliente.
    Métodos:
    - ejecutar: Ejecuta el caso de uso para abonar un pago a un cliente.
"""
class AbonarClienteUseCase:
    """Registra un pago del cliente contra su saldo de crédito."""

    def __init__(self, cliente_repo: ClienteRepository):
        self._repo = cliente_repo

    async def ejecutar(self, data: AbonarClienteInput) -> Cliente:
        cliente = await _cargar(self._repo, data.cliente_id)
        cliente.abonar(data.monto)
        await self._repo.decrementar_saldo(data.cliente_id, data.monto)
        return cliente

"""
    CambiarLimiteCreditoInput
    Descripcion: Clase que representa los datos de entrada para cambiar el límite de crédito de un cliente.
    Atributos:
    - cliente_id: ID del cliente.
    - nuevo_limite: Nuevo límite de crédito.
"""
@dataclass
class CambiarLimiteCreditoInput:
    cliente_id: UUID
    nuevo_limite: Decimal

"""
    CambiarLimiteCreditoUseCase
    Descripcion: Clase que representa el caso de uso para cambiar el límite de crédito de un cliente.
    Métodos:
    - ejecutar: Ejecuta el caso de uso para cambiar el límite de crédito de un cliente.
"""
class CambiarLimiteCreditoUseCase:
    """
        Método para ejecutar el caso de uso para cambiar el límite de crédito de un cliente.
    """
    def __init__(self, cliente_repo: ClienteRepository):
        self._repo = cliente_repo

    """
        Método para ejecutar el caso de uso para cambiar el límite de crédito de un cliente.
        Parámetros:
        - data: Datos de entrada para cambiar el límite de crédito de un cliente.
        Retorna:
        - Cliente: Cliente con el límite de crédito actualizado.
    """
    async def ejecutar(self, data: CambiarLimiteCreditoInput) -> Cliente:
        cliente = await _cargar(self._repo, data.cliente_id)
        cliente.cambiar_limite_credito(data.nuevo_limite)
        await self._repo.actualizar_limite_credito(data.cliente_id, data.nuevo_limite)
        return cliente

"""
    ConsultarClienteUseCase
    Descripcion: Clase que representa el caso de uso para consultar un cliente.
    Métodos:
    - ejecutar: Ejecuta el caso de uso para consultar un cliente.
"""
class ConsultarClienteUseCase:
    def __init__(self, cliente_repo: ClienteRepository):
        self._repo = cliente_repo

    """
        Método para ejecutar el caso de uso para consultar un cliente.
        Parámetros:
        - data: Datos de entrada para consultar un cliente.
        Retorna:
        - Cliente: Cliente consultado.
    """
    async def ejecutar(self, data: CambiarLimiteCreditoInput) -> Cliente:
        cliente = await _cargar(self._repo, data.cliente_id)
        # Valida que el nuevo límite no quede por debajo del saldo actual.
        cliente.cambiar_limite_credito(data.nuevo_limite)
        await self._repo.actualizar_limite_credito(data.cliente_id, data.nuevo_limite)
        return cliente
