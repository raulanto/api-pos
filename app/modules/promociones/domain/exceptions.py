class PromocionNoEncontrada(Exception):
    pass


class PromocionInvalida(Exception):
    """Los parámetros de la promoción no son coherentes con su `tipo`, o la
    lista de objetivos está vacía, o el nombre ya existe."""
    pass
