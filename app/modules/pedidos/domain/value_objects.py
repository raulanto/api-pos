from enum import Enum


class TipoPedido(str, Enum):
    MOSTRADOR = "mostrador"     # se arma en el POS, sin entrega
    DOMICILIO = "domicilio"     # envío a domicilio (tiene máquina de entrega)
    RECOGER = "recoger"         # el cliente pasa a recogerlo


class CanalPedido(str, Enum):
    POS = "pos"
    WEB = "web"
    TELEFONO = "telefono"


class EstadoPedido(str, Enum):
    BORRADOR = "borrador"       # cotización editable, precios NO congelados
    CONFIRMADO = "confirmado"   # cliente aceptó; precios congelados
    FACTURADO = "facturado"     # tiene `venta_id` (terminal)
    CANCELADO = "cancelado"     # terminal


class EstadoEntrega(str, Enum):
    """Sólo aplica a `tipo=domicilio` (y `recoger`). Ortogonal a `EstadoPedido`."""
    PENDIENTE = "pendiente"
    EN_PREPARACION = "en_preparacion"
    EN_REPARTO = "en_reparto"
    ENTREGADO = "entregado"
    FALLIDO = "fallido"


# Transiciones válidas de la entrega. `fallido` se puede reintentar.
TRANSICIONES_ENTREGA: dict[EstadoEntrega, set[EstadoEntrega]] = {
    EstadoEntrega.PENDIENTE: {EstadoEntrega.EN_PREPARACION, EstadoEntrega.FALLIDO},
    EstadoEntrega.EN_PREPARACION: {
        EstadoEntrega.EN_REPARTO, EstadoEntrega.ENTREGADO, EstadoEntrega.FALLIDO,
    },
    EstadoEntrega.EN_REPARTO: {EstadoEntrega.ENTREGADO, EstadoEntrega.FALLIDO},
    EstadoEntrega.FALLIDO: {EstadoEntrega.EN_PREPARACION, EstadoEntrega.EN_REPARTO},
    EstadoEntrega.ENTREGADO: set(),
}
