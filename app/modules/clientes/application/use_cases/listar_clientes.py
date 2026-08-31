from app.modules.clientes.application.dtos import FiltroClientes
from app.modules.clientes.application.ports.cliente_repository import ClienteRepository
from app.shared.responses import Page, PageParams, Sort


class ListarClientesUseCase:
    """Lista clientes paginados. No arma el sobre HTTP: devuelve un `Page`."""

    def __init__(self, cliente_repo: ClienteRepository):
        self._repo = cliente_repo

    async def ejecutar(
        self, filtro: FiltroClientes, paginacion: PageParams, orden: Sort
    ) -> Page:
        return await self._repo.listar(filtro, paginacion, orden)
