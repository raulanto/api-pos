from app.modules.clientes.application.dtos import FiltroClientes, Paginacion, Pagina
from app.modules.clientes.application.ports.cliente_repository import ClienteRepository

"""
    ListarClientesUseCase
    Descripcion: Clase que representa el caso de uso para listar clientes.
    Métodos:
    - ejecutar: Ejecuta el caso de uso para listar clientes.
"""
class ListarClientesUseCase:
    """
        Método para ejecutar el caso de uso para listar clientes.
        Parámetros:
        - filtro: Filtro para listar clientes.
        - paginacion: Paginacion para listar clientes.
        Retorna:
        - Pagina: Pagina de clientes.
    """
    def __init__(self, cliente_repo: ClienteRepository):
        self._repo = cliente_repo

    """
        Método para ejecutar el caso de uso para listar clientes.
        Parámetros:
        - filtro: Filtro para listar clientes.
        - paginacion: Paginacion para listar clientes.
        Retorna:
        - Pagina: Pagina de clientes.
    """
    async def ejecutar(self, filtro: FiltroClientes, paginacion: Paginacion) -> Pagina:
        return await self._repo.listar(filtro, paginacion)
