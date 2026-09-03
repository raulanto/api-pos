from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4
from app.modules.inventario.domain.value_objects import TipoProducto


"""
    Entidad que representa un producto.

    @param id: ID del producto.
    @param sku: SKU del producto.
    @param codigo_barras: Código de barras del producto.
    @param nombre: Nombre del producto.
    @param descripcion: Descripción del producto.
    @param categoria_id: ID de la categoría.
    @param unidad_medida: Unidad de medida del producto.
    @param precio_venta: Precio de venta del producto.
    @param costo: Costo del producto.
    @param impuesto_tasa: Tasa de impuesto.
    @param tipo: Tipo de producto.
    @param permite_stock_negativo: Permite stock negativo.
    @param activo: Indica si el producto está activo.
    @param created_at: Fecha de creación.
    @return: Instancia de la clase Producto.
"""
@dataclass
class Producto:
    id: UUID
    sku: str
    codigo_barras: str | None
    nombre: str
    descripcion: str | None
    categoria_id: UUID
    unidad_medida: str
    precio_venta: Decimal
    costo: Decimal
    impuesto_tasa: Decimal
    tipo: TipoProducto
    permite_stock_negativo: bool
    activo: bool
    created_at: datetime = field(default_factory=datetime.utcnow)

    # Relaciones embebidas opcionales (`?include=categoria,existencias`).
    categoria: object | None = field(default=None, compare=False, repr=False)
    existencias: object | None = field(default=None, compare=False, repr=False)


    """
    Método estático para crear un producto.

    @param sku: SKU del producto.
    @param nombre: Nombre del producto.
    @param categoria_id: ID de la categoría.
    @param unidad_medida: Unidad de medida del producto.
    @param precio_venta: Precio de venta del producto.
    @param costo: Costo del producto.
    @param impuesto_tasa: Tasa de impuesto.
    @param permite_stock_negativo: Permite stock negativo.
    @param codigo_barras: Código de barras del producto.
    @param descripcion: Descripción del producto.
    @return: Instancia de la clase Producto.
    """
    @staticmethod
    def crear(
        sku: str, nombre: str, categoria_id: UUID, unidad_medida: str,
        precio_venta: Decimal, costo: Decimal, impuesto_tasa: Decimal,
        permite_stock_negativo: bool = False, codigo_barras: str | None = None,
        descripcion: str | None = None
    ) -> "Producto":
        return Producto(
            id=uuid4(),
            sku=sku,
            codigo_barras=codigo_barras,
            nombre=nombre,
            descripcion=descripcion,
            categoria_id=categoria_id,
            unidad_medida=unidad_medida,
            precio_venta=precio_venta,
            costo=costo,
            impuesto_tasa=impuesto_tasa,
            tipo=TipoProducto.SIMPLE,
            permite_stock_negativo=permite_stock_negativo,
            activo=True
        )

    """
    Método para actualizar un producto.

    @param self: Instancia de la clase Producto.
    @param nombre: Nombre del producto.
    @param descripcion: Descripción del producto.
    @param categoria_id: ID de la categoría.
    @param unidad_medida: Unidad de medida del producto.
    @param precio_venta: Precio de venta del producto.
    @param costo: Costo del producto.
    @param impuesto_tasa: Tasa de impuesto.
    @param permite_stock_negativo: Permite stock negativo.
    @param codigo_barras: Código de barras del producto.
    @param cambiar_codigo_barras: Indica si se debe cambiar el código de barras.
    @return: None
    """
    def actualizar(
        self,
        nombre: str | None = None,
        descripcion: str | None = None,
        categoria_id: UUID | None = None,
        unidad_medida: str | None = None,
        precio_venta: Decimal | None = None,
        costo: Decimal | None = None,
        impuesto_tasa: Decimal | None = None,
        permite_stock_negativo: bool | None = None,
        codigo_barras: str | None = None,
        cambiar_codigo_barras: bool = False,
        sku: str | None = None,
        tipo: TipoProducto | None = None,
        cambiar_descripcion: bool = False,
    ) -> None:
        if sku is not None:
            self.sku = sku
        if nombre is not None:
            self.nombre = nombre
        if cambiar_descripcion:
            self.descripcion = descripcion          # permite volver a NULL
        elif descripcion is not None:
            self.descripcion = descripcion
        if categoria_id is not None:
            self.categoria_id = categoria_id
        if unidad_medida is not None:
            self.unidad_medida = unidad_medida
        if precio_venta is not None:
            self.precio_venta = precio_venta
        if costo is not None:
            self.costo = costo
        if impuesto_tasa is not None:
            self.impuesto_tasa = impuesto_tasa
        if tipo is not None:
            self.tipo = tipo
        if permite_stock_negativo is not None:
            self.permite_stock_negativo = permite_stock_negativo
        if cambiar_codigo_barras:
            self.codigo_barras = codigo_barras

    """
    Método para desactivar un producto.

    @param self: Instancia de la clase Producto.
    @return: None
    """
    def desactivar(self) -> None:
        self.activo = False

    """
    Método para reactivar un producto dado de baja.

    @param self: Instancia de la clase Producto.
    @return: None
    """
    def activar(self) -> None:
        self.activo = True
