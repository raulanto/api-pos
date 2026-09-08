from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.modules.ventas.domain.value_objects import EstadoVenta
from app.shared.responses import Page  # re-export por compatibilidad

__all__ = ["FiltroVentas", "FiltroTurnos", "Page"]


@dataclass
class FiltroVentas:
    sucursal_id: UUID | None = None
    caja_turno_id: UUID | None = None
    cliente_id: UUID | None = None
    telefono: str | None = None            # historial de compras por teléfono (monedero)
    estado: EstadoVenta | None = None
    desde: datetime | None = None
    hasta: datetime | None = None


@dataclass
class FiltroTurnos:
    """Histórico de turnos de caja (arqueos, diferencias por cajero)."""
    sucursal_id: UUID | None = None
    caja_id: UUID | None = None
    usuario_id: UUID | None = None
    estado: str | None = None
    desde: datetime | None = None
    hasta: datetime | None = None
