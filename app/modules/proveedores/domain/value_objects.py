from enum import Enum


class TipoPersona(str, Enum):
    FISICA = "fisica"
    MORAL = "moral"


class CondicionesPago(str, Enum):
    CONTADO = "contado"
    CREDITO = "credito"


class EstadoPedidoProveedor(str, Enum):
    BORRADOR = "borrador"
    ENVIADO = "enviado"
    CONFIRMADO = "confirmado"    # ponytail: sin transición cableada (ver guía)
    PARCIAL = "parcial"
    RECIBIDO = "recibido"
    CANCELADO = "cancelado"


class EstadoRecepcion(str, Enum):
    COMPLETA = "completa"
    PARCIAL = "parcial"
    CON_DEFECTOS = "con_defectos"


class MotivoDefecto(str, Enum):
    DANADO = "danado"
    CADUCADO = "caducado"
    INCOMPLETO = "incompleto"
    ERROR_PROVEEDOR = "error_proveedor"
    OTRO = "otro"


class AccionDefecto(str, Enum):
    DEVOLUCION = "devolucion"
    MERMA = "merma"
    ACEPTADO_CON_DESCUENTO = "aceptado_con_descuento"


class EstadoDevolucionProveedor(str, Enum):
    PENDIENTE = "pendiente"
    ENVIADA = "enviada"
    CERRADA = "cerrada"


class ResultadoDevolucion(str, Enum):
    ACEPTADA_PROVEEDOR = "aceptada_proveedor"
    RECHAZADA_PROVEEDOR = "rechazada_proveedor"


class TipoResolucionDevolucion(str, Enum):
    REEMPLAZO = "reemplazo"
    NOTA_CREDITO = "nota_credito"
    REEMBOLSO = "reembolso"
