from abc import ABC, abstractmethod
from uuid import UUID

from app.modules.clientes.domain.entities import MonederoCuenta, MonederoMovimiento
from app.shared.responses import Page, PageParams, Sort


class MonederoRepository(ABC):
    """Persistencia del monedero. Escrituras con `flush`; el commit lo cierra
    `get_db()`."""

    @abstractmethod
    async def obtener_por_telefono(
        self, telefono: str, para_actualizar: bool = False,
    ) -> MonederoCuenta | None:
        """`para_actualizar=True` bloquea la fila (`FOR UPDATE`) para mover el
        saldo sin condición de carrera."""
        ...

    @abstractmethod
    async def crear_cuenta(self, cuenta: MonederoCuenta) -> None: ...

    @abstractmethod
    async def guardar_saldo(self, cuenta: MonederoCuenta) -> None:
        """UPDATE monedero_cuenta SET saldo = cuenta.saldo WHERE id = ..."""
        ...

    @abstractmethod
    async def registrar_movimiento(self, movimiento: MonederoMovimiento) -> None: ...

    @abstractmethod
    async def listar_movimientos(
        self, cuenta_id: UUID, paginacion: PageParams, orden: Sort,
    ) -> Page: ...

    @abstractmethod
    async def movimientos_de_venta(self, venta_id: UUID) -> list[MonederoMovimiento]:
        """Movimientos generados por una venta (para revertirlos al anular)."""
        ...
