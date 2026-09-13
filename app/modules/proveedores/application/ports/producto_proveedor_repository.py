from abc import ABC, abstractmethod
from uuid import UUID

from app.modules.proveedores.domain.entities import ProductoProveedor


class ProductoProveedorRepository(ABC):
    @abstractmethod
    async def obtener_por_id(self, id_: UUID) -> ProductoProveedor | None: ...

    @abstractmethod
    async def obtener_por_par(
        self, producto_id: UUID, proveedor_id: UUID,
    ) -> ProductoProveedor | None: ...

    @abstractmethod
    async def guardar(self, pp: ProductoProveedor) -> None: ...

    @abstractmethod
    async def actualizar(self, pp: ProductoProveedor) -> None: ...

    @abstractmethod
    async def listar_por_producto(
        self, producto_id: UUID, incluir_inactivos: bool = False,
    ) -> list[ProductoProveedor]: ...

    @abstractmethod
    async def listar_por_proveedor(
        self, proveedor_id: UUID, incluir_inactivos: bool = False,
    ) -> list[ProductoProveedor]: ...

    @abstractmethod
    async def obtener_principal(self, producto_id: UUID) -> ProductoProveedor | None: ...

    @abstractmethod
    async def listar_principales_activos(self) -> list[ProductoProveedor]:
        """Todos los vínculos `es_proveedor_principal=true` activos —
        candidatos del motor de reorden."""
        ...
