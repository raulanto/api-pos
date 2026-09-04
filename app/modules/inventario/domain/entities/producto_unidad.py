from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4


"""
    Entidad que representa una PRESENTACIÓN de venta de un producto.

    El producto tiene una unidad base implícita (factor 1, precio =
    `producto.precio_venta`, código = `producto.codigo_barras`). Cada
    `ProductoUnidad` es una presentación ADICIONAL: "Reja x24", "Six-pack", etc.

    @param id: ID de la presentación.
    @param producto_id: ID del producto (siempre en unidades base).
    @param nombre: Nombre visible ("Reja x24").
    @param factor: Unidades base que representa 1 de esta presentación (> 0).
    @param precio_venta: Precio de venta de 1 de esta presentación.
    @param codigo_barras: Código de barras propio de la presentación (opcional).
    @param activo: Baja lógica (se conserva para las ventas históricas).
"""
@dataclass
class ProductoUnidad:
    id: UUID
    producto_id: UUID
    nombre: str
    unidad_medida: str
    factor: Decimal
    precio_venta: Decimal
    codigo_barras: str | None = None
    activo: bool = True
    created_at: datetime = None  # type: ignore[assignment]

    @property
    def unidades_por_base(self) -> Decimal | None:
        """Cuántas de esta presentación entran en 1 unidad base (= 1 / factor)."""
        if not self.factor:
            return None
        return (Decimal("1") / self.factor).quantize(Decimal("0.0001"))

    @staticmethod
    def crear(
        producto_id: UUID, nombre: str, unidad_medida: str, factor: Decimal,
        precio_venta: Decimal, codigo_barras: str | None = None,
    ) -> "ProductoUnidad":
        return ProductoUnidad(
            id=uuid4(),
            producto_id=producto_id,
            nombre=nombre,
            unidad_medida=unidad_medida,
            factor=factor,
            precio_venta=precio_venta,
            codigo_barras=codigo_barras,
            activo=True,
            created_at=datetime.now(timezone.utc),
        )

    def actualizar(
        self,
        nombre: str | None = None,
        unidad_medida: str | None = None,
        factor: Decimal | None = None,
        precio_venta: Decimal | None = None,
        codigo_barras: str | None = None,
        cambiar_codigo_barras: bool = False,
    ) -> None:
        if nombre is not None:
            self.nombre = nombre
        if unidad_medida is not None:
            self.unidad_medida = unidad_medida
        if factor is not None:
            self.factor = factor
        if precio_venta is not None:
            self.precio_venta = precio_venta
        if cambiar_codigo_barras:
            self.codigo_barras = codigo_barras

    def desactivar(self) -> None:
        self.activo = False
