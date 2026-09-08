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
    MONEDERO = "monedero"     # paga con el saldo de monedero del teléfono de la venta

class MetodoDevolucion(str, Enum):
    EFECTIVO = "efectivo"      # sale plata del cajón (descuenta del arqueo)
    TARJETA = "tarjeta"        # reverso a la tarjeta (no toca el cajón)
    CREDITO = "credito"        # baja la deuda del cliente
    MONEDERO = "monedero"      # reintegra al monedero del teléfono

class TipoMovimientoCaja(str, Enum):
    RETIRO = "retiro"          # efectivo que sale del cajón (a caja fuerte/gerencia)
    INGRESO = "ingreso"        # efectivo que entra sin ser venta (refuerzo de fondo)
    GASTO = "gasto"            # efectivo gastado desde el cajón (papelería, etc.)
