from abc import ABC, abstractmethod
from decimal import Decimal
from uuid import UUID

from app.modules.proveedores.domain.entities import DevolucionProveedor
from app.modules.proveedores.application.dtos import FiltroDevoluciones
from app.shared.responses import Page, PageParams, Sort


class DevolucionProveedorRepository(ABC):
    @abstractmethod
    async def obtener_por_id(self, devolucion_id: UUID) -> DevolucionProveedor | None: ...

    @abstractmethod
    async def guardar(self, devolucion: DevolucionProveedor) -> None: ...

    @abstractmethod
    async def actualizar(self, devolucion: DevolucionProveedor) -> None: ...

    @abstractmethod
    async def cantidad_ya_devuelta(self, recepcion_detalle_id: UUID) -> Decimal:
        """Σ `cantidad` de las líneas de devolución (de cualquier devolución)
        que ya reclamaron ese `recepcion_detalle_id`."""
        ...

    @abstractmethod
    async def listar(
        self, filtro: FiltroDevoluciones, paginacion: PageParams, orden: Sort,
    ) -> Page: ...

    @abstractmethod
    async def resumen_por_proveedor(self, proveedor_id: UUID) -> dict:
        """Conteo de devoluciones por `resultado`, para el reporte de Fase 5."""
        ...
