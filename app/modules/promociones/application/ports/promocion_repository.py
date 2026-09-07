from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from app.modules.promociones.domain.entities import Promocion
from app.modules.promociones.application.dtos import FiltroPromociones
from app.shared.responses import Page, PageParams, Sort


class PromocionRepository(ABC):
    @abstractmethod
    async def obtener_por_id(self, promocion_id: UUID) -> Promocion | None: ...

    @abstractmethod
    async def listar(
        self, filtro: FiltroPromociones, paginacion: PageParams, orden: Sort
    ) -> Page: ...

    @abstractmethod
    async def listar_vigentes(
        self, momento: datetime, sucursal_id: UUID
    ) -> list[Promocion]:
        """Activas, dentro de la ventana de fechas y de la sucursal (o sin
        sucursal), con sus objetivos cargados."""
        ...

    @abstractmethod
    async def existe_nombre(self, nombre: str, excluir_id: UUID | None = None) -> bool: ...

    @abstractmethod
    async def crear(self, promocion: Promocion) -> Promocion: ...

    @abstractmethod
    async def actualizar(self, promocion: Promocion) -> None:
        """Persiste la cabecera y reemplaza la lista de objetivos."""
        ...
