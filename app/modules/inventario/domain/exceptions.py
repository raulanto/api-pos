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
