from abc import ABC, abstractmethod
from uuid import UUID

from app.modules.inventario.domain.entities import ProductoImagen


class ImagenRepository(ABC):
    @abstractmethod
    async def listar_por_producto(self, producto_id: UUID) -> list[ProductoImagen]: ...

    @abstractmethod
    async def listar_por_unidad(self, producto_unidad_id: UUID) -> list[ProductoImagen]: ...

    @abstractmethod
    async def obtener(self, imagen_id: UUID) -> ProductoImagen | None: ...

    @abstractmethod
    async def crear(self, imagen: ProductoImagen) -> None: ...

    @abstractmethod
    async def actualizar(self, imagen: ProductoImagen) -> None: ...

    @abstractmethod
    async def eliminar(self, imagen_id: UUID) -> None: ...

    @abstractmethod
    async def desmarcar_principal(
        self, producto_id: UUID | None, producto_unidad_id: UUID | None,
        excepto_id: UUID | None = None,
    ) -> None:
        """Pone `es_principal=False` en todas las imágenes del mismo dueño
        (excepto `excepto_id`), para que sólo quede una marcada."""
        ...
