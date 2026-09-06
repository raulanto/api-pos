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
    @param SIMPLE: Producto unitario común (se vende de a piezas enteras).
    @param FRACCIONABLE: Se vende en fracciones de la unidad base (litros, kg,
        metros) y/o en presentaciones (`producto_unidad`).
    @param KIT: Se arma con otros productos (BOM); no lleva stock propio.
    @param SERVICIO: No mueve inventario (mano de obra, envíos, cargos).
    @return: Instancia de la clase TipoProducto.
"""
class TipoProducto(str, Enum):
    SIMPLE = "simple"
    FRACCIONABLE = "fraccionable"
    KIT = "kit"
    SERVICIO = "servicio"

    @property
    def mueve_stock(self) -> bool:
        """SERVICIO no descuenta ni repone existencia."""
        return self is not TipoProducto.SERVICIO


"""
    Enum para la magnitud física que mide una unidad del catálogo.
    Sirve para agrupar unidades convertibles entre sí y para reportes.
    @param CONTEO: Piezas, cajas, rejas... (adimensional).
    @param MASA: Gramos, kilos...
    @param VOLUMEN: Mililitros, litros...
    @param LONGITUD: Centímetros, metros...
    @param TIEMPO: Horas, días (servicios).
    @return: Instancia de la clase TipoMagnitud.
"""
class TipoMagnitud(str, Enum):
    CONTEO = "conteo"
    MASA = "masa"
    VOLUMEN = "volumen"
    LONGITUD = "longitud"
    TIEMPO = "tiempo"


"""
    Estado de una instancia física abierta (envase destapado que se vende en
    fracciones de la unidad base).
    @param ABIERTA: en uso, con saldo disponible.
    @param AGOTADA: su saldo llegó a 0 por consumo/venta/merma.
    @param DESCARTADA: se dio de baja el envase con saldo remanente (derrame,
        contaminación); el remanente se registró como MERMA.
"""
class EstadoInstancia(str, Enum):
    ABIERTA = "abierta"
    AGOTADA = "agotada"
    DESCARTADA = "descartada"
