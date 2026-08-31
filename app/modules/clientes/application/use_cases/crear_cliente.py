from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID
from app.modules.clientes.domain.entities import Cliente
from app.modules.clientes.application.ports.cliente_repository import ClienteRepository

@dataclass
class CrearClienteInput:
    sucursal_id: UUID
    nombre: str
    email: str | None = None
    telefono: str | None = None
    rfc_identificacion: str | None = None
    limite_credito: Decimal = Decimal("0")

class CrearClienteUseCase:
    def __init__(self, cliente_repo: ClienteRepository):
        self._cliente_repo = cliente_repo

    async def ejecutar(self, data: CrearClienteInput) -> Cliente:
        cliente = Cliente.crear(
            sucursal_id=data.sucursal_id,
            nombre=data.nombre,
            email=data.email,
            telefono=data.telefono,
            rfc_identificacion=data.rfc_identificacion,
            limite_credito=data.limite_credito
        )
        await self._cliente_repo.guardar(cliente)
        return cliente
