from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4
from app.modules.inventario.domain.value_objects import TipoMovimiento


"""
    Entidad que representa un movimiento de inventario.

    @param id: ID del movimiento.
    @param producto_id: ID del producto.
    @param sucursal_id: ID de la sucursal.
    @param tipo: Tipo de movimiento.
    @param cantidad: Cantidad del movimiento.
    @param costo_unitario: Costo unitario.
    @param referencia_tipo: Tipo de referencia.
    @param referencia_id: ID de la referencia.
    @param usuario_id: ID del usuario.
    @param motivo: Motivo del movimiento.
    @param created_at: Fecha de creación.
    @return: Instancia de la clase MovimientoInventario.
"""
@dataclass
class MovimientoInventario:
    id: UUID
    producto_id: UUID
    sucursal_id: UUID
    tipo: TipoMovimiento
    cantidad: Decimal
    costo_unitario: Decimal | None
    referencia_tipo: str
    referencia_id: UUID | None
    usuario_id: UUID
    motivo: str | None
    created_at: datetime = field(default_factory=datetime.utcnow)

    # Relaciones embebidas opcionales (`?include=producto,usuario`).
    producto: object | None = field(default=None, compare=False, repr=False)
    usuario: object | None = field(default=None, compare=False, repr=False)


    """
    Método estático para crear un movimiento de inventario.

    @param producto_id: ID del producto.
    @param sucursal_id: ID de la sucursal.
    @param tipo: Tipo de movimiento.
    @param cantidad: Cantidad del movimiento.
    @param referencia_tipo: Tipo de referencia.
    @param usuario_id: ID del usuario.
    @param referencia_id: ID de la referencia.
    @param costo_unitario: Costo unitario.
    @param motivo: Motivo del movimiento.
    @return: Instancia de la clase MovimientoInventario.

    """
    @staticmethod
    def crear(
        producto_id: UUID, sucursal_id: UUID, tipo: TipoMovimiento, cantidad: Decimal,
        referencia_tipo: str, usuario_id: UUID, referencia_id: UUID | None = None,
        costo_unitario: Decimal | None = None, motivo: str | None = None
    ) -> "MovimientoInventario":
        if cantidad < 0:
            raise ValueError("La cantidad del movimiento debe ser siempre positiva.")
        
        return MovimientoInventario(
            id=uuid4(),
            producto_id=producto_id,
            sucursal_id=sucursal_id,
            tipo=tipo,
            cantidad=cantidad,
            costo_unitario=costo_unitario,
            referencia_tipo=referencia_tipo,
            referencia_id=referencia_id,
            usuario_id=usuario_id,
            motivo=motivo
        )
