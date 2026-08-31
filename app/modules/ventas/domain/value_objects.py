from enum import Enum

class EstadoVenta(str, Enum):
    PAGADA = "pagada"
    PENDIENTE_PAGO = "pendiente_pago"
    CANCELADA = "cancelada"
    DEVUELTA_PARCIAL = "devuelta_parcial"
    DEVUELTA_TOTAL = "devuelta_total"

class MetodoPago(str, Enum):
    EFECTIVO = "efectivo"
    TARJETA_CREDITO = "tarjeta_credito"
    TARJETA_DEBITO = "tarjeta_debito"
    TRANSFERENCIA = "transferencia"
    CREDITO = "credito"
