from uuid import UUID
from app.modules.clientes.domain.entities import Cliente
from app.modules.clientes.domain.exceptions import ClienteNoEncontrado
from app.modules.clientes.application.ports.cliente_repository import ClienteRepository

class ObtenerClienteUseCase:
    def __init__(self, cliente_repo: ClienteRepository):
        self._cliente_repo = cliente_repo

    async def ejecutar(self, cliente_id: UUID) -> Cliente:
        cliente = await self._cliente_repo.obtener_por_id(cliente_id)
        if not cliente:
            raise ClienteNoEncontrado(f"No existe el cliente con id {cliente_id}")
        return cliente
