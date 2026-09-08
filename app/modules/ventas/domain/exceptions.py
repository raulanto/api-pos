class VentaYaCancelada(Exception):
    pass

class VentaSinLineas(Exception):
    pass

class VentaNoEncontrada(Exception):
    pass

class CajaNoAbierta(Exception):
    pass

class VentaCreditoSinCliente(Exception):
    pass

class SucursalNoOperativa(Exception):
    """La sucursal está inactiva o tiene `permite_ventas = False`: no se puede
    abrir turno de caja ni registrar ventas ahí."""
    pass

# --- Turno de caja ---
class TurnoNoEncontrado(Exception):
    pass

class TurnoYaAbierto(Exception):
    """El usuario ya tiene un turno de caja abierto."""
    pass

class TurnoYaCerrado(Exception):
    pass

class TurnoDeOtraSucursal(Exception):
    """El caja_turno_id no pertenece a la sucursal del usuario."""
    pass

class CierreTurnoNoPermitido(Exception):
    """Sólo el dueño del turno (o un rol global) puede cerrarlo."""
    pass

# --- Anulación ---
class AnulacionNoPermitida(Exception):
    """El usuario no puede anular esta venta (turno cerrado y sin rol de gerente),
    o la venta tiene devoluciones parciales."""
    pass

# --- Devoluciones parciales ---
class DevolucionInvalida(Exception):
    """La devolución no cuadra: línea que no es de la venta, cantidad <= 0,
    turno de la devolución no operable, etc."""
    pass

class VentaNoDevolvible(Exception):
    """La venta está cancelada o ya devuelta por completo."""
    pass

class CantidadDevolucionExcedida(Exception):
    """Se pidió devolver más de lo que queda por devolver en esa línea."""
    pass

# --- Descuento manual en POS ---
class DescuentoManualNoAutorizado(Exception):
    """El usuario no tiene el permiso `ventas.descuento_manual`."""
    pass

class DescuentoManualExcedeTope(Exception):
    """El % de descuento manual supera el tope del rol."""
    pass

class MotivoDescuentoRequerido(Exception):
    """Hay descuento manual (`descuento_linea`/`descuento_total`) sin `motivo_descuento`."""
    pass
