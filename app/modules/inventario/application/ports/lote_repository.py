from abc import ABC, abstractmethod
from datetime import date
from decimal import Decimal
from uuid import UUID

from app.modules.inventario.domain.entities import Lote, ExistenciaLote


class LoteRepository(ABC):
    """Maneja tanto el catálogo de lotes (`lote`) como su saldo por sucursal
    (`existencia_lote`), que están fuertemente acoplados."""

    # ---- catálogo de lotes ----
    @abstractmethod
    async def obtener(self, lote_id: UUID) -> Lote | None: ...

    @abstractmethod
    async def obtener_por_codigo(self, producto_id: UUID, codigo_lote: str) -> Lote | None: ...

    @abstractmethod
    async def listar_por_producto(
        self, producto_id: UUID, incluir_inactivos: bool = False
    ) -> list[Lote]: ...

    @abstractmethod
    async def por_vencer(
        self, hasta: date, sucursal_ids: list[UUID] | None = None,
        incluir_vencidos: bool = True,
    ) -> list[tuple[Lote, UUID, Decimal]]:
        """Lotes con `fecha_caducidad <= hasta` y saldo > 0.
        Devuelve (lote, sucursal_id, cantidad) por cada existencia_lote."""
        ...

    @abstractmethod
    async def crear(self, lote: Lote) -> None: ...

    @abstractmethod
    async def actualizar(self, lote: Lote) -> None: ...

    # ---- saldo por lote (existencia_lote) ----
    @abstractmethod
    async def saldo(
        self, sucursal_id: UUID, lote_id: UUID, para_actualizar: bool = False,
    ) -> Decimal:
        """Saldo del lote en la sucursal (0 si no hay fila). `para_actualizar`
        bloquea la fila de `existencia_lote`."""
        ...

    @abstractmethod
    async def lotes_fefo(
        self, producto_id: UUID, sucursal_id: UUID, para_actualizar: bool = False,
    ) -> list[tuple[UUID, Decimal]]:
        """(lote_id, cantidad) de los lotes con saldo > 0 de ese producto y
        sucursal, ordenados FEFO: `fecha_caducidad` ascendente, NULLs al final,
        y a igualdad por antigüedad de alta."""
        ...

    @abstractmethod
    async def ajustar_saldo(
        self, producto_id: UUID, sucursal_id: UUID, lote_id: UUID, delta: Decimal,
    ) -> Decimal:
        """Suma `delta` (positivo o negativo) al saldo del lote en la sucursal,
        creando la fila si no existe. Devuelve el saldo resultante."""
        ...

    @abstractmethod
    async def listar_saldos(
        self, producto_id: UUID, sucursal_id: UUID | None = None,
        solo_con_saldo: bool = True,
    ) -> list[ExistenciaLote]: ...
