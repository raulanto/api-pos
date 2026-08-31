from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from sqlalchemy.exc import IntegrityError

from app.modules.clientes.domain.entities import Cliente
from app.modules.clientes.domain.exceptions import EmailClienteDuplicado
from app.modules.clientes.application.ports.cliente_repository import ClienteRepository


"""
    CrearClienteInput
    Descripcion: Clase que representa los datos de entrada para crear un cliente.
    Atributos:
    - sucursal_id: ID de la sucursal.
    - nombre: Nombre del cliente.
    - email: Email del cliente.
    - telefono: Telefono del cliente.
    - rfc_identificacion: RFC del cliente.
    - limite_credito: Límite de crédito del cliente.
"""
@dataclass
class CrearClienteInput:
    sucursal_id: UUID
    nombre: str
    email: str | None = None
    telefono: str | None = None
    rfc_identificacion: str | None = None
    limite_credito: Decimal = Decimal("0")


"""
    CrearClienteUseCase
    Descripcion: Clase que representa el caso de uso para crear un cliente.
    Métodos:
    - ejecutar: Ejecuta el caso de uso para crear un cliente.
"""
class CrearClienteUseCase:
    def __init__(self, cliente_repo: ClienteRepository):
        self._cliente_repo = cliente_repo

    """
        Método para ejecutar el caso de uso para crear un cliente.
        Parámetros:
        - data: Datos de entrada para crear un cliente.
        Retorna:
        - Cliente: Cliente creado.
    """
    async def ejecutar(self, data: CrearClienteInput) -> Cliente:
        if data.email:
            existente = await self._cliente_repo.buscar_por_email(data.email)
            if existente is not None:
                raise EmailClienteDuplicado(
                    f"Ya existe un cliente activo con el email '{data.email}'"
                )

        cliente = Cliente.crear(
            sucursal_id=data.sucursal_id,
            nombre=data.nombre,
            email=data.email,
            telefono=data.telefono,
            rfc_identificacion=data.rfc_identificacion,
            limite_credito=data.limite_credito,
        )
        try:
            await self._cliente_repo.guardar(cliente)
        except IntegrityError:
            raise EmailClienteDuplicado(
                f"Ya existe un cliente con el email '{data.email}'"
            )
        return cliente
