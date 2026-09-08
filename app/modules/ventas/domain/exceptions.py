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

# --- Caja física (terminal) ---
class CajaNoEncontrada(Exception):
    """No existe la caja/terminal, o no pertenece a la sucursal."""
    pass

class CajaInactiva(Exception):
    """La caja/terminal está desactivada: no se puede abrir un turno ahí."""
    pass

# --- Turno de caja ---
class TurnoNoEncontrado(Exception):
    pass

class TurnoYaAbierto(Exception):
    """El usuario (o la terminal) ya tiene un turno de caja abierto."""
    pass

class TurnoYaCerrado(Exception):
    pass

class TurnoDeOtraSucursal(Exception):
    """El caja_turno_id no pertenece a la sucursal del usuario."""
    pass

class CierreTurnoNoPermitido(Exception):
    """Sólo el dueño del turno (o `caja.forzar_cierre`) puede cerrarlo."""
    pass

class NotaCierreRequerida(Exception):
    """El cierre dejó |diferencia| >= umbral y no vino `nota_cierre`."""
    pass

class MovimientoTurnoCerrado(Exception):
    """Se intentó registrar un retiro/ingreso/gasto en un turno no abierto."""
    pass

class MotivoMovimientoRequerido(Exception):
    """Un retiro o gasto necesita `motivo`."""
    pass

class DenominacionNoCuadra(Exception):
    """La suma del desglose por denominación no coincide con el saldo declarado."""
    pass

class TurnoNoRequiereConciliacion(Exception):
    """Se pidió conciliar un turno que no está `cerrado_con_diferencia`."""
    pass

class ConciliacionNoPermitida(Exception):
    """Falta el permiso `caja.autorizar_diferencia`."""
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
