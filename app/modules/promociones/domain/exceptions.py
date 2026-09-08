class PromocionNoEncontrada(Exception):
    pass


class CuponNoEncontrado(Exception):
    """No hay cupón activo con ese código."""
    pass


class CuponVencido(Exception):
    """El cupón está fuera de su ventana de vigencia o desactivado."""
    pass


class CuponAgotado(Exception):
    """El cupón alcanzó su límite de usos (total o por persona)."""
    pass


class PromocionInvalida(Exception):
    """Los parámetros de la promoción no son coherentes con su `tipo`, o la
    lista de objetivos está vacía, o el nombre ya existe."""
    pass
