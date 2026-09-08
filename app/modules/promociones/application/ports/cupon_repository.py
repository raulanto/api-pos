from abc import ABC, abstractmethod
from uuid import UUID

from app.modules.promociones.domain.entities import Cupon, CuponUso


class CuponRepository(ABC):
    @abstractmethod
    async def obtener_por_codigo(
        self, codigo: str, para_actualizar: bool = False,
    ) -> Cupon | None: ...

    @abstractmethod
    async def listar_por_promocion(self, promocion_id: UUID) -> list[Cupon]: ...

    @abstractmethod
    async def crear(self, cupon: Cupon) -> None: ...

    @abstractmethod
    async def actualizar(self, cupon: Cupon) -> None: ...

    @abstractmethod
    async def contar_usos(self, cupon_id: UUID) -> int: ...

    @abstractmethod
    async def contar_usos_persona(
        self, cupon_id: UUID, telefono: str | None, cliente_id: UUID | None,
    ) -> int: ...

    @abstractmethod
    async def registrar_uso(self, uso: CuponUso) -> None: ...

    @abstractmethod
    async def borrar_usos_de_venta(self, venta_id: UUID) -> None: ...
