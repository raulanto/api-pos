from enum import Enum


class TipoMovimientoMonedero(str, Enum):
    """Cada fila del ledger `monedero_movimiento`."""
    ACUMULACION = "acumulacion"           # la venta generó saldo
    CONSUMO = "consumo"                   # se pagó una venta con el monedero
    REVERSO_ACUMULACION = "reverso_acumulacion"  # anulación: se quita lo generado
    REVERSO_CONSUMO = "reverso_consumo"   # anulación/devolución: se reintegra
    AJUSTE = "ajuste"                     # ajuste manual (+/-)
