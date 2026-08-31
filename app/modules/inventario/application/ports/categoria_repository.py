from abc import ABC, abstractmethod
from uuid import UUID
from app.modules.inventario.domain.entities import Categoria

class CategoriaRepository(ABC):
    @abstractmethod
    async def guardar(self, categoria: Categoria) -> None: ...

    @abstractmethod
    async def actualizar(self, categoria: Categoria) -> None: ...

    @abstractmethod
    async def obtener_por_id(self, categoria_id: UUID) -> Categoria | None: ...

    @abstractmethod
    async def listar(
        self,
        activo: bool | None = None,
        categoria_padre_id: UUID | None = None,
    ) -> list[Categoria]: ...

    @abstractmethod
    async def tiene_productos_activos(self, categoria_id: UUID) -> bool: ...
