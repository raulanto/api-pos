from abc import ABC, abstractmethod
from decimal import Decimal
from uuid import UUID

from app.modules.clientes.domain.entities import Cliente
from app.modules.clientes.application.dtos import FiltroClientes, Paginacion, Pagina

"""
    ClienteRepository
    Descripcion: Interfaz que define las operaciones del repositorio de clientes.
    Métodos:
    - guardar: Guarda un cliente.
    - actualizar: Actualiza un cliente.
    - obtener_por_id: Obtiene un cliente por ID.
    - buscar_por_email: Busca un cliente por email.
    - listar: Lista los clientes.
    - incrementar_saldo: Incrementa el saldo del cliente.
    - decrementar_saldo: Decrementa el saldo del cliente.
    - actualizar_limite_credito: Actualiza el límite de crédito del cliente.
    - desactivar: Desactiva un cliente.
"""
class ClienteRepository(ABC):
    """
        Método para guardar un cliente.
        Parámetros:
        - cliente: Cliente a guardar.
        Retorna:
        - None
    """
    @abstractmethod
    async def guardar(self, cliente: Cliente) -> None: ...

    """
        Método para actualizar un cliente.
        Parámetros:
        - cliente: Cliente a actualizar.
        Retorna:
        - None
    """
    @abstractmethod
    async def actualizar(self, cliente: Cliente) -> None: ...

    """
        Método para obtener un cliente por ID.
        Parámetros:
        - cliente_id: ID del cliente.
        Retorna:
        - Cliente | None: Cliente encontrado o None.
    """
    @abstractmethod
    async def obtener_por_id(self, cliente_id: UUID) -> Cliente | None: ...

    """
        Método para buscar un cliente por email.
        Parámetros:
        - email: Email del cliente.
        - solo_activos: Solo buscar clientes activos.
        Retorna:
        - Cliente | None: Cliente encontrado o None.
    """
    @abstractmethod
    async def buscar_por_email(self, email: str, solo_activos: bool = True) -> Cliente | None: ...

    """
        Método para listar los clientes.
        Parámetros:
        - filtro: Filtros de busqueda.
        - paginacion: Paginacion.
        Retorna:
        - Pagina: Página con los clientes.
    """
    @abstractmethod
    async def listar(self, filtro: FiltroClientes, paginacion: Paginacion) -> Pagina: ...

    """
        Método para incrementar el saldo del cliente.
        Parámetros:
        - cliente_id: ID del cliente.
        - monto: Monto a incrementar.
        Retorna:
        - None
    """
    @abstractmethod
    async def incrementar_saldo(self, cliente_id: UUID, monto: Decimal) -> None: ...

    """
        Método para decrementar el saldo del cliente.
        Parámetros:
        - cliente_id: ID del cliente.
        - monto: Monto a decrementar.
        Retorna:
        - None
    """
    @abstractmethod
    async def decrementar_saldo(self, cliente_id: UUID, monto: Decimal) -> None: ...

    """
        Método para actualizar el límite de crédito del cliente.
        Parámetros:
        - cliente_id: ID del cliente.
        - nuevo_limite: Nuevo límite de crédito.
        Retorna:
        - None
    """
    @abstractmethod
    async def actualizar_limite_credito(self, cliente_id: UUID, nuevo_limite: Decimal) -> None: ...

    """
        Método para desactivar un cliente.
        Parámetros:
        - cliente_id: ID del cliente.
        Retorna:
        - None
    """
    @abstractmethod
    async def desactivar(self, cliente_id: UUID) -> None: ...
