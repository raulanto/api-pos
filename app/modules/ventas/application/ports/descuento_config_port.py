from abc import ABC, abstractmethod
from decimal import Decimal
from uuid import UUID


class DescuentoConfigPort(ABC):
    """Config del descuento manual en POS. El permiso `ventas.descuento_manual`
    es el gate; esto sólo aporta el tope de % por rol."""

    @abstractmethod
    async def pct_max_para_rol(self, rol_id: UUID) -> Decimal | None:
        """% máximo de descuento manual para el rol. `None` = sin tope (no hay
        fila para el rol, o la fila tiene `pct_max` NULL)."""
        ...
