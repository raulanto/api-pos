class PedidoError(Exception):
    """Base de los errores de dominio del módulo pedidos."""


class PedidoNoEncontrado(PedidoError):
    pass


class PedidoSinLineas(PedidoError):
    pass


class TransicionPedidoInvalida(PedidoError):
    """Cambio de estado no permitido para el estado actual del pedido/entrega."""


class PedidoNoEditable(PedidoError):
    """Se intentó editar un pedido que ya no está en `borrador`."""


class PedidoYaFacturado(PedidoError):
    pass


class DireccionEnvioRequerida(PedidoError):
    """`tipo=domicilio` sin `direccion_texto`."""


class EntregaNoAplica(PedidoError):
    """Operación de entrega sobre un pedido que no es de domicilio/recoger."""


class ServicioSinResponsable(PedidoError):
    """Se intentó confirmar un pedido con una línea de servicio sin `asignado_a`."""


class ResponsableInvalido(PedidoError):
    """`asignado_a` no es un usuario activo, o la línea no es un servicio."""


class AnticipoInvalido(PedidoError):
    pass


class MotivoDescuentoRequerido(PedidoError):
    """Hay descuento manual (`descuento_total`/`descuento_linea`) sin motivo."""
