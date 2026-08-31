from uuid import UUID
from app.modules.clientes.domain.entities import Cliente
from app.modules.clientes.domain.exceptions import ClienteNoEncontrado
from app.modules.clientes.application.ports.cliente_repository import ClienteRepository


"""
    ObtenerClienteUseCase
    Descripcion: Clase que representa el caso de uso para obtener un cliente.
    Métodos:
    - ejecutar: Ejecuta el caso de uso para obtener un cliente.
"""
class ObtenerClienteUseCase:
    """
        Método para obtener un cliente por ID.
        Parámetros:
        - cliente_id: ID del cliente.
        Retorna:
        - Cliente: Cliente obtenido.
    """
    def __init__(self, cliente_repo: ClienteRepository):
        self._cliente_repo = cliente_repo

    """
        Método para ejecutar el caso de uso para obtener un cliente.
        Parámetros:
        - cliente_id: ID del cliente.
        Retorna:
        - Cliente: Cliente obtenido.
    """
    async def ejecutar(self, cliente_id: UUID) -> Cliente:
        cliente = await self._cliente_repo.obtener_por_id(cliente_id)
        if not cliente:
            raise ClienteNoEncontrado(f"No existe el cliente con id {cliente_id}")
        return cliente
