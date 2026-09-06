class CategoriaNoEncontrada(Exception):
    pass

class ProductoNoEncontrado(Exception):
    pass

class MovimientoNoEncontrado(Exception):
    pass

class ProductoInactivo(Exception):
    pass

class StockInsuficiente(Exception):
    pass

class SkuDuplicado(Exception):
    pass

class CodigoBarrasDuplicado(Exception):
    pass

class AjusteSinCantidadFinal(Exception):
    """Un movimiento de AJUSTE necesita `cantidad_final` (el saldo objetivo)."""
    pass

class TransferenciaInvalida(Exception):
    """La sucursal de origen y destino no pueden ser la misma, u otros datos inválidos."""
    pass

class ExistenciaNoEncontrada(Exception):
    pass

class CategoriaConProductosActivos(Exception):
    """No se puede desactivar una categoría que aún tiene productos activos."""
    pass

class JerarquiaCategoriaInvalida(Exception):
    """`categoria_padre_id` genera un ciclo o se apunta a sí misma."""
    pass

class ProductoConStockActivo(Exception):
    """No se puede desactivar un producto con existencia > 0 sin confirmación explícita."""
    pass

class ProductoConHistorial(Exception):
    """No se puede BORRAR físicamente el producto: tiene movimientos de
    inventario o está referenciado por ventas u otros registros históricos.
    Usar la baja lógica (`/desactivar`) en su lugar."""
    pass

class KitInvalido(Exception):
    """El producto no es de tipo `kit`, o se intenta dejarlo `simple` con componentes."""
    pass

class ComponenteInvalido(Exception):
    """El componente no existe, está inactivo, es el propio kit, o es a su vez un kit."""
    pass

class ComponenteDuplicado(Exception):
    """Ese producto ya es componente del kit."""
    pass

class ComponenteNoEncontrado(Exception):
    """La línea kit/componente pedida no existe."""
    pass

class ProductoEsComponenteDeKit(Exception):
    """No se puede desactivar un producto que es componente de un kit activo."""
    pass

class UnidadNoEncontrada(Exception):
    """La presentación (producto_unidad) pedida no existe para ese producto."""
    pass

class UnidadInvalida(Exception):
    """`factor` <= 0, o se intenta ponerle presentaciones a un kit."""
    pass

class UnidadDuplicada(Exception):
    """Ya existe una presentación con ese nombre para el producto."""
    pass

class CodigoBarrasUnidadDuplicado(Exception):
    """El código de barras ya lo usa otro producto o presentación."""
    pass


class UnidadMedidaNoEncontrada(Exception):
    """La unidad de medida del catálogo pedida no existe."""
    pass


class UnidadMedidaDuplicada(Exception):
    """Ya existe una unidad de medida con ese `codigo`."""
    pass


class UnidadMedidaEnUso(Exception):
    """No se puede desactivar/eliminar: hay productos o presentaciones que la usan."""
    pass


class CantidadNoVendible(Exception):
    """La cantidad viola las reglas de fraccionamiento del producto
    (no es entera cuando no admite fracción, o no es múltiplo del incremento)."""
    pass


class ImagenNoEncontrada(Exception):
    """La imagen pedida no existe para ese producto/presentación."""
    pass


class ImagenInvalida(Exception):
    """La imagen no indica exactamente un dueño (producto XOR presentación), o
    el dueño indicado no existe."""
    pass


class LoteNoEncontrado(Exception):
    """El lote pedido no existe (o no pertenece al producto indicado)."""
    pass


class LoteDuplicado(Exception):
    """Ya existe un lote activo con ese `codigo_lote` para el producto."""
    pass


class LoteRequerido(Exception):
    """El producto lleva control por lote y el movimiento no indicó a qué lote
    entra (ENTRADA) o de qué lote sale (AJUSTE)."""
    pass


class LoteInvalido(Exception):
    """No se puede activar el control por lote (hay stock sin lotear), o el lote
    indicado no aplica al movimiento (producto/sucursal distintos, inactivo...)."""
    pass
