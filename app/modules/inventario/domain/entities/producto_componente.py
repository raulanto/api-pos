from dataclasses import dataclass, field
from decimal import Decimal
from uuid import UUID


"""
    Entidad que representa una línea de la receta de un kit:
    `cantidad` unidades de `producto_componente_id` por cada unidad de
    `producto_kit_id`.

    @param producto_kit_id: ID del producto kit.
    @param producto_componente_id: ID del producto componente.
    @param cantidad: Unidades del componente por unidad de kit (> 0).
"""
@dataclass
class ProductoComponente:
    producto_kit_id: UUID
    producto_componente_id: UUID
    cantidad: Decimal

    # Relación embebida opcional (`?include=producto`); la puebla el mapper.
    producto: object | None = field(default=None, compare=False, repr=False)
