class RecursoNoEncontrado(Exception):
    pass

class NombreRecursoEnUso(Exception):
    """Otro recurso activo de la sucursal ya usa ese nombre."""
    pass

class EmpleadoServicioNoEncontrado(Exception):
    pass

class ServicioNoAgendable(Exception):
    """El producto no es `tipo=servicio` o no tiene `duracion_minutos` seteado."""
    pass

class EmpleadoNoCalificado(Exception):
    """El empleado no está en `empleado_servicio` activo para ese servicio."""
    pass

class SucursalCruzadaNoPermitida(Exception):
    """Se pidió disponibilidad cruzada y el servicio no la tiene activada."""
    pass

class NingunEmpleadoDisponible(Exception):
    """No hubo error, pero cero candidatos elegibles (la cita queda
    SIN_EMPLEADO_DISPONIBLE; esta excepción es informativa para el caller)."""
    pass

class CitaNoOfertable(Exception):
    """Sólo se oferta una cita en `por_asignar` o `sin_empleado_disponible`."""
    pass

class OfertaNoVigente(Exception):
    """La `cita_asignacion` ya no está `ofrecida` (superada/rechazada/aceptada)."""
    pass

class AsignacionNoPropia(Exception):
    """Un empleado intentó responder la oferta de otro."""
    pass

class EmpleadoYaAsignado(Exception):
    """El empleado ya tiene otra cita ASIGNADA/EN_PROCESO que se solapa."""
    pass

class RecursoNoDisponible(Exception):
    """El recurso ya está ocupado en ese rango (constraint EXCLUDE de BD)."""
    pass

class CitaNoEncontrada(Exception):
    pass

class TransicionCitaInvalida(Exception):
    pass

class CitaYaFacturada(Exception):
    pass

class CitaNoFacturable(Exception):
    """Sólo se vincula a una venta una cita `completada` sin venta previa."""
    pass
