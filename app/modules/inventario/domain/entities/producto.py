from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4
from app.modules.inventario.domain.value_objects import TipoProducto
from app.modules.inventario.domain.exceptions import CantidadNoVendible


"""
    Entidad que representa un producto.

    @param id: ID del producto.
    @param sku: SKU del producto.
    @param codigo_barras: Código de barras del producto.
    @param nombre: Nombre del producto.
    @param descripcion: Descripción del producto.
    @param categoria_id: ID de la categoría.
    @param unidad_medida: Unidad de medida del producto (texto, se conserva como
        fallback / rótulo mientras `unidad_medida_id` no esté poblado).
    @param precio_venta: Precio de venta del producto.
    @param costo: Costo del producto.
    @param impuesto_tasa: Tasa de impuesto.
    @param tipo: Tipo de producto.
    @param permite_stock_negativo: Permite stock negativo.
    @param activo: Indica si el producto está activo.
    @param created_at: Fecha de creación.
    @param unidad_medida_id: FK al catálogo `unidad_medida` (opcional).
    @param permite_venta_fraccionada: Si se puede vender una cantidad no entera
        de la unidad base.
    @param incremento_minimo_venta: Si se define, toda cantidad vendida debe ser
        múltiplo de este valor (p. ej. 0.050 kg, 50 ml).
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
    unidad_medida_id: UUID | None = None
    permite_venta_fraccionada: bool = False
    incremento_minimo_venta: Decimal | None = None
    # Control por lote: si está activo, cada ENTRADA debe indicar un lote y las
    # SALIDAS descuentan por FEFO (primero el que vence antes).
    requiere_lote: bool = False
    # Instancia física abierta: si está activo, las ventas a granel consumen de
    # envases abiertos (`instancia_abierta`); `instancia_capacidad_default` es la
    # capacidad con la que se auto-abre un envase al vender.
    rastrea_instancia_abierta: bool = False
    instancia_capacidad_default: Decimal | None = None

    # Relaciones embebidas opcionales
    # (`?include=categoria,existencias,componentes,unidades,imagenes`).
    categoria: object | None = field(default=None, compare=False, repr=False)
    existencias: object | None = field(default=None, compare=False, repr=False)
    componentes: object | None = field(default=None, compare=False, repr=False)
    unidades: object | None = field(default=None, compare=False, repr=False)
    imagenes: object | None = field(default=None, compare=False, repr=False)
    # Siempre presente (no depende de `?include=`): la imagen marcada como
    # `es_principal` de la galería del producto, o None si no tiene ninguna.
    imagen_principal: object | None = field(default=None, compare=False, repr=False)


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
    @param tipo: Tipo de producto (por defecto SIMPLE).
    @param unidad_medida_id: FK al catálogo de unidades (opcional).
    @param permite_venta_fraccionada: Permite cantidades no enteras.
    @param incremento_minimo_venta: Múltiplo obligatorio de la cantidad vendida.
    @return: Instancia de la clase Producto.
    """
    @staticmethod
    def crear(
        sku: str, nombre: str, categoria_id: UUID, unidad_medida: str,
        precio_venta: Decimal, costo: Decimal, impuesto_tasa: Decimal,
        permite_stock_negativo: bool = False, codigo_barras: str | None = None,
        descripcion: str | None = None, tipo: TipoProducto = TipoProducto.SIMPLE,
        unidad_medida_id: UUID | None = None,
        permite_venta_fraccionada: bool = False,
        incremento_minimo_venta: Decimal | None = None,
        requiere_lote: bool = False,
        rastrea_instancia_abierta: bool = False,
        instancia_capacidad_default: Decimal | None = None,
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
            tipo=tipo,
            permite_stock_negativo=permite_stock_negativo,
            activo=True,
            unidad_medida_id=unidad_medida_id,
            permite_venta_fraccionada=(
                permite_venta_fraccionada or tipo == TipoProducto.FRACCIONABLE
            ),
            incremento_minimo_venta=incremento_minimo_venta,
            requiere_lote=requiere_lote,
            rastrea_instancia_abierta=rastrea_instancia_abierta,
            instancia_capacidad_default=instancia_capacidad_default,
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
    @param sku: Nuevo SKU.
    @param tipo: Nuevo tipo de producto.
    @param cambiar_descripcion: Permite fijar `descripcion` a NULL.
    @param unidad_medida_id: Nueva FK al catálogo de unidades.
    @param cambiar_unidad_medida_id: Permite fijar `unidad_medida_id` a NULL.
    @param permite_venta_fraccionada: Nuevo valor del flag.
    @param incremento_minimo_venta: Nuevo múltiplo obligatorio.
    @param cambiar_incremento_minimo_venta: Permite fijar el incremento a NULL.
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
        unidad_medida_id: UUID | None = None,
        cambiar_unidad_medida_id: bool = False,
        permite_venta_fraccionada: bool | None = None,
        incremento_minimo_venta: Decimal | None = None,
        cambiar_incremento_minimo_venta: bool = False,
        requiere_lote: bool | None = None,
        rastrea_instancia_abierta: bool | None = None,
        instancia_capacidad_default: Decimal | None = None,
        cambiar_instancia_capacidad_default: bool = False,
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
        if cambiar_unidad_medida_id:
            self.unidad_medida_id = unidad_medida_id
        elif unidad_medida_id is not None:
            self.unidad_medida_id = unidad_medida_id
        if precio_venta is not None:
            self.precio_venta = precio_venta
        if costo is not None:
            self.costo = costo
        if impuesto_tasa is not None:
            self.impuesto_tasa = impuesto_tasa
        if tipo is not None:
            self.tipo = tipo
            if tipo == TipoProducto.FRACCIONABLE:
                self.permite_venta_fraccionada = True
        if permite_venta_fraccionada is not None:
            self.permite_venta_fraccionada = permite_venta_fraccionada
        if requiere_lote is not None:
            self.requiere_lote = requiere_lote
        if rastrea_instancia_abierta is not None:
            self.rastrea_instancia_abierta = rastrea_instancia_abierta
        if cambiar_instancia_capacidad_default:
            self.instancia_capacidad_default = instancia_capacidad_default
        elif instancia_capacidad_default is not None:
            self.instancia_capacidad_default = instancia_capacidad_default
        if cambiar_incremento_minimo_venta:
            self.incremento_minimo_venta = incremento_minimo_venta
        elif incremento_minimo_venta is not None:
            self.incremento_minimo_venta = incremento_minimo_venta
        if permite_stock_negativo is not None:
            self.permite_stock_negativo = permite_stock_negativo
        if cambiar_codigo_barras:
            self.codigo_barras = codigo_barras

    """
    Valida que una cantidad a vender/mover respete las reglas de fraccionamiento.

    - Si el producto no admite venta fraccionada, la cantidad debe ser entera.
    - Si define `incremento_minimo_venta`, la cantidad debe ser múltiplo exacto.

    @param cantidad: Cantidad expresada en la unidad base del producto.
    @raises CantidadNoVendible: si la cantidad no cumple las reglas.
    @return: None
    """
    def validar_cantidad_vendible(self, cantidad: Decimal) -> None:
        if cantidad is None or cantidad <= 0:
            raise CantidadNoVendible("La cantidad debe ser mayor a 0.")
        if not self.permite_venta_fraccionada and cantidad != cantidad.to_integral_value():
            raise CantidadNoVendible(
                f"{self.nombre} no admite venta fraccionada: la cantidad debe ser entera."
            )
        inc = self.incremento_minimo_venta
        if inc is not None and inc > 0 and (cantidad % inc) != 0:
            raise CantidadNoVendible(
                f"La cantidad de {self.nombre} debe ser múltiplo de {inc}."
            )

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
