from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from uuid import UUID


"""
    Saldo de stock de un LOTE en una sucursal.

    Es el desglose por lote de `Existencia`: para un producto con control por
    lote, `existencia.cantidad` (agregado) == suma de `existencia_lote.cantidad`
    de ese producto y sucursal.

    @param id: ID de la fila.
    @param producto_id: Producto (redundante con `lote.producto_id`, se guarda
        para filtrar/consultar rápido).
    @param sucursal_id: Sucursal.
    @param lote_id: Lote.
    @param cantidad: Saldo del lote en esa sucursal (unidad base).
    @param updated_at: Última modificación.
"""
@dataclass
class ExistenciaLote:
    id: UUID
    producto_id: UUID
    sucursal_id: UUID
    lote_id: UUID
    cantidad: Decimal
    updated_at: datetime = field(default_factory=datetime.utcnow)

    # Relación embebida opcional: el lote (`?include=lote`), la puebla el mapper.
    lote: object | None = field(default=None, compare=False, repr=False)
