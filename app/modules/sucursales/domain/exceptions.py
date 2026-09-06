class SucursalNoEncontrada(Exception):
    pass


class NombreSucursalDuplicado(Exception):
    """Ya existe una sucursal (activa o inactiva) con ese nombre."""
    pass


class CodigoSucursalDuplicado(Exception):
    """Ya existe una sucursal con ese `codigo`."""
    pass


class SucursalConUsuariosActivos(Exception):
    """No se puede desactivar una sucursal con usuarios activos asignados."""
    pass


class SucursalPadreNoEncontrada(Exception):
    """El `sucursal_padre_id` indicado no existe."""
    pass


class JerarquiaSucursalInvalida(Exception):
    """El cambio de padre genera un ciclo o la sucursal se apunta a sí misma."""
    pass


class SucursalNoOperativa(Exception):
    """La sucursal está inactiva o tiene `permite_ventas = False`: no se puede
    abrir turno de caja ni registrar ventas ahí."""
    pass
