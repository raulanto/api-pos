from enum import Enum


class EstadoCita(str, Enum):
    POR_ASIGNAR = "por_asignar"                  # ofertada a 0+ empleados, sin ganador
    ASIGNADA = "asignada"                         # un empleado aceptó
    EN_PROCESO = "en_proceso"                     # el servicio arrancó
    COMPLETADA = "completada"                     # terminado, disponible para cobro
    CANCELADA = "cancelada"                       # terminal
    NO_SHOW = "no_show"                           # terminal
    SIN_EMPLEADO_DISPONIBLE = "sin_empleado_disponible"  # todos rechazaron / cero elegibles


class EstadoAsignacion(str, Enum):
    OFRECIDA = "ofrecida"
    ACEPTADA = "aceptada"      # ganó la cola
    RECHAZADA = "rechazada"    # el empleado la rechazó explícitamente
    SUPERADA = "superada"      # otro empleado aceptó primero; no es un rechazo real


class TipoExcepcion(str, Enum):
    BLOQUEO = "bloqueo"                    # el empleado no atiende (total o parcial del día)
    HORARIO_ESPECIAL = "horario_especial"  # reemplaza el horario base ese día
