class ProveedorNoEncontrado(Exception):
    pass

class CodigoProveedorEnUso(Exception):
    pass

class DiasCreditoRequerido(Exception):
    """`condiciones_pago=credito` necesita `dias_credito` > 0."""
    pass

class ProductoProveedorNoEncontrado(Exception):
    pass

class ProductoProveedorYaExiste(Exception):
    """Ya existe un vínculo activo entre ese producto y ese proveedor."""
    pass

class YaHayProveedorPrincipal(Exception):
    """Otro proveedor ya es el principal (activo) de ese producto."""
    pass

class PedidoProveedorNoEncontrado(Exception):
    pass

class PedidoProveedorSinLineas(Exception):
    pass

class PedidoNoEditable(Exception):
    """Agregar líneas / cancelar un pedido fuera del estado que lo permite."""
    pass

class TransicionPedidoProveedorInvalida(Exception):
    pass

class RecepcionProveedorNoEncontrada(Exception):
    pass

class RecepcionSinLineas(Exception):
    pass

class DefectoInvalido(Exception):
    """`motivo_defecto`/`accion_defecto` faltante (si hay defectuosos) o
    sobrante (si no los hay)."""
    pass

class DevolucionProveedorNoEncontrada(Exception):
    pass

class CantidadDevolucionExcedeDefecto(Exception):
    """La cantidad a devolver (sumada a lo ya devuelto de esa línea) supera lo
    defectuoso registrado en la recepción."""
    pass

class TransicionDevolucionInvalida(Exception):
    pass
