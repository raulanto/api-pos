from app.modules.clientes.application.dtos import FiltroClientes, Paginacion, Pagina
from app.modules.clientes.application.ports.cliente_repository import ClienteRepository


class ListarClientesUseCase:
    def __init__(self, cliente_repo: ClienteRepository):
        self._repo = cliente_repo

    async def ejecutar(self, filtro: FiltroClientes, paginacion: Paginacion) -> Pagina:
        return await self._repo.listar(filtro, paginacion)
