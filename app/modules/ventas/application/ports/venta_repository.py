from abc import ABC, abstractmethod
from decimal import Decimal
from uuid import UUID
from app.modules.ventas.domain.entities import Venta
from app.modules.ventas.domain.value_objects import EstadoVenta
from app.modules.ventas.application.dtos import FiltroVentas
from app.shared.responses import Page, PageParams, Sort

class VentaRepository(ABC):
    @abstractmethod
    async def guardar(self, venta: Venta) -> None: ...

    @abstractmethod
    async def obtener_por_id(
        self, venta_id: UUID, includes: frozenset[str] = frozenset()
    ) -> Venta | None: ...

    @abstractmethod
    async def obtener_por_idempotency_key(self, key: str) -> Venta | None: ...

    @abstractmethod
    async def actualizar_estado(self, venta_id: UUID, estado: EstadoVenta) -> None: ...

    @abstractmethod
    async def registrar_monedero_generado(self, venta_id: UUID, monto: Decimal) -> None:
        """Congela en la venta el saldo de monedero que generó (post-persistencia)."""
        ...

    @abstractmethod
    async def registrar_devolucion(self, venta: "Venta") -> None:
        """Persiste `estado` de la venta y `cantidad_devuelta` de cada línea tras
        una devolución (el resto de la venta es inmutable)."""
        ...

    @abstractmethod
    async def listar(
        self,
        filtro: FiltroVentas,
        paginacion: PageParams,
        orden: Sort,
        includes: frozenset[str] = frozenset(),
    ) -> Page: ...
