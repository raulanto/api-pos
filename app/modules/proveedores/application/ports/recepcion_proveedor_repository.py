from abc import ABC, abstractmethod
from uuid import UUID

from app.modules.proveedores.domain.entities import (
    RecepcionProveedor, RecepcionProveedorLinea,
)
from app.modules.proveedores.application.dtos import FiltroRecepciones
from app.shared.responses import Page, PageParams, Sort


class RecepcionProveedorRepository(ABC):
    @abstractmethod
    async def obtener_por_id(self, recepcion_id: UUID) -> RecepcionProveedor | None: ...

    @abstractmethod
    async def obtener_linea(self, linea_id: UUID) -> RecepcionProveedorLinea | None: ...

    @abstractmethod
    async def guardar(self, recepcion: RecepcionProveedor) -> None: ...

    @abstractmethod
    async def listar(
        self, filtro: FiltroRecepciones, paginacion: PageParams, orden: Sort,
    ) -> Page: ...

    @abstractmethod
    async def resumen_defectos_por_proveedor(self, proveedor_id: UUID) -> dict:
        """Agregados para el reporte de Fase 5: total recibido, total
        defectuoso, tiempos de entrega reales de las recepciones con pedido."""
        ...
