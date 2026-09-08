class ClienteNoEncontrado(Exception):
    pass

class LimiteCreditoExcedido(Exception):
    pass

class EmailClienteDuplicado(Exception):
    """Ya existe otro cliente activo con ese email."""
    pass

class AbonoInvalido(Exception):
    """El abono no es positivo o excede el saldo de crédito pendiente."""
    pass

class LimiteCreditoInvalido(Exception):
    """El nuevo límite de crédito quedaría por debajo del saldo actual."""
    pass

class ClienteConDeuda(Exception):
    """No se puede desactivar un cliente con saldo_credito > 0."""
    pass

class MonederoCuentaNoEncontrada(Exception):
    """No hay cuenta de monedero para ese teléfono."""
    pass

class SaldoMonederoInsuficiente(Exception):
    """El monedero no tiene saldo para cubrir el consumo/ajuste."""
    pass

class MovimientoMonederoInvalido(Exception):
    """Monto no positivo, teléfono vacío, o ajuste cero."""
    pass
