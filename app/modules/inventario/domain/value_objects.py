from enum import Enum

class TipoMovimiento(str, Enum):
    ENTRADA = "entrada"
    SALIDA = "salida"
    AJUSTE = "ajuste"
    MERMA = "merma"
    TRANSFERENCIA = "transferencia"

class TipoProducto(str, Enum):
    SIMPLE = "simple"
    KIT = "kit"
