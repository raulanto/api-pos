from abc import ABC, abstractmethod
from decimal import Decimal
from uuid import UUID

from app.shared.responses import Page, PageParams, Sort
from app.modules.ventas.domain.entities import (
    Caja, CajaTurno, CajaMovimiento, DenominacionConteo,
)
from app.modules.ventas.application.dtos import FiltroTurnos


class CajaRepository(ABC):
    """CRUD de cajas físicas (terminales) de una sucursal."""

    @abstractmethod
    async def obtener_por_id(self, caja_id: UUID) -> Caja | None: ...

    @abstractmethod
    async def listar(
        self, sucursal_id: UUID, incluir_inactivas: bool = False
    ) -> list[Caja]: ...

    @abstractmethod
    async def guardar(self, caja: Caja) -> None: ...

    @abstractmethod
    async def actualizar(self, caja: Caja) -> None: ...

    @abstractmethod
    async def nombre_en_uso(
        self, sucursal_id: UUID, nombre: str, excluir_id: UUID | None = None
    ) -> bool:
        """True si otra caja ACTIVA de la sucursal ya usa ese nombre."""
        ...


class CajaTurnoRepository(ABC):
    @abstractmethod
    async def obtener_por_id(self, turno_id: UUID) -> CajaTurno | None: ...

    @abstractmethod
    async def guardar(self, turno: CajaTurno) -> None: ...

    @abstractmethod
    async def actualizar(self, turno: CajaTurno) -> None: ...

    @abstractmethod
    async def obtener_abierto_de_usuario(
        self, usuario_id: UUID, sucursal_id: UUID
    ) -> CajaTurno | None: ...

    @abstractmethod
    async def total_efectivo_del_turno(self, turno_id: UUID) -> Decimal:
        """Suma de pagos en efectivo de las ventas no canceladas del turno."""
        ...

    @abstractmethod
    async def total_devoluciones_efectivo_del_turno(self, turno_id: UUID) -> Decimal:
        """Suma de devoluciones en efectivo hechas EN este turno (sale plata del
        cajón, descuenta del arqueo)."""
        ...

    @abstractmethod
    async def contar_ventas_del_turno(self, turno_id: UUID) -> int: ...

    # --- Movimientos de caja (retiro/ingreso/gasto) ---
    @abstractmethod
    async def registrar_movimiento(self, mov: CajaMovimiento) -> None: ...

    @abstractmethod
    async def listar_movimientos(self, turno_id: UUID) -> list[CajaMovimiento]: ...

    @abstractmethod
    async def movimientos_por_tipo(self, turno_id: UUID) -> dict[str, Decimal]:
        """{'ingreso': X, 'retiro': Y, 'gasto': Z} (sólo los tipos con monto)."""
        ...

    @abstractmethod
    async def movimientos_neto_del_turno(self, turno_id: UUID) -> Decimal:
        """ingresos - retiros - gastos."""
        ...

    # --- Desglose por denominación ---
    @abstractmethod
    async def guardar_denominaciones(
        self, turno_id: UUID, momento: str, conteos: list[DenominacionConteo]
    ) -> None: ...

    @abstractmethod
    async def listar_denominaciones(
        self, turno_id: UUID, momento: str | None = None
    ) -> list[DenominacionConteo]: ...

    # --- Histórico / dashboard ---
    @abstractmethod
    async def listar_turnos(
        self, filtro: FiltroTurnos, paginacion: PageParams, orden: Sort
    ) -> Page: ...

    @abstractmethod
    async def efectivo_en_sucursal(self, sucursal_id: UUID) -> Decimal:
        """Σ saldo esperado de los turnos ABIERTOS de la sucursal (efectivo en
        el cajón, en tiempo real)."""
        ...
