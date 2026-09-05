from abc import ABC, abstractmethod
from uuid import UUID

from app.modules.inventario.domain.entities import UnidadMedida


class UnidadMedidaRepository(ABC):
    @abstractmethod
    async def listar(self, incluir_inactivas: bool = False) -> list[UnidadMedida]: ...

    @abstractmethod
    async def obtener(self, unidad_id: UUID) -> UnidadMedida | None: ...

    @abstractmethod
    async def obtener_por_codigo(self, codigo: str) -> UnidadMedida | None: ...

    @abstractmethod
    async def crear(self, unidad: UnidadMedida) -> None: ...

    @abstractmethod
    async def actualizar(self, unidad: UnidadMedida) -> None: ...

    @abstractmethod
    async def esta_en_uso(self, unidad_id: UUID) -> bool: ...
