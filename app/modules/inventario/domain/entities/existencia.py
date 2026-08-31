from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from uuid import UUID


"""
    Entidad que representa la existencia de un producto en una sucursal.

    @param id: ID de la existencia.
    @param producto_id: ID del producto.
    @param sucursal_id: ID de la sucursal.
    @param cantidad: Cantidad de producto.
    @param stock_minimo: Stock mínimo.
    @param stock_maximo: Stock máximo.
    @param updated_at: Fecha de actualización.
    
    @return: Instancia de la clase Existencia.
    """
@dataclass
class Existencia:
    id: UUID
    producto_id: UUID
    sucursal_id: UUID
    cantidad: Decimal
    stock_minimo: Decimal
    stock_maximo: Decimal | None
    updated_at: datetime = field(default_factory=datetime.utcnow)
