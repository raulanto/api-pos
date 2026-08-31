from enum import Enum


"""
    Enum para los tipos de movimiento.
    @param ENTRADA: Movimiento de entrada.
    @param SALIDA: Movimiento de salida.
    @param AJUSTE: Movimiento de ajuste.
    @param MERMA: Movimiento de merma.
    @param TRANSFERENCIA: Movimiento de transferencia.
    @return: Instancia de la clase TipoMovimiento.
"""
class TipoMovimiento(str, Enum):
    ENTRADA = "entrada"
    SALIDA = "salida"
    AJUSTE = "ajuste"
    MERMA = "merma"
    TRANSFERENCIA = "transferencia"

"""
    Enum para los tipos de producto.
    @param SIMPLE: Producto simple.
    @param KIT: Kit de productos.
    @return: Instancia de la clase TipoProducto.
"""
class TipoProducto(str, Enum):
    SIMPLE = "simple"
    KIT = "kit"
