from dataclasses import dataclass, field
from datetime import date, datetime, time, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from app.modules.agenda.domain.value_objects import (
    EstadoCita, EstadoAsignacion, TipoExcepcion,
)
from app.modules.agenda.domain.exceptions import (
    CitaNoOfertable, OfertaNoVigente, TransicionCitaInvalida, CitaNoFacturable,
)


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------------- #
# Catálogo
# --------------------------------------------------------------------------- #
@dataclass
class Recurso:
    id: UUID
    sucursal_id: UUID
    nombre: str
    tipo: str | None = None
    activo: bool = True
    created_at: datetime = field(default_factory=_ahora)

    @staticmethod
    def crear(sucursal_id: UUID, nombre: str, tipo: str | None = None) -> "Recurso":
        nombre = (nombre or "").strip()
        if not nombre:
            raise ValueError("El recurso necesita un nombre")
        return Recurso(id=uuid4(), sucursal_id=sucursal_id, nombre=nombre, tipo=tipo)

    def renombrar(self, nombre: str) -> None:
        nombre = (nombre or "").strip()
        if not nombre:
            raise ValueError("El recurso necesita un nombre")
        self.nombre = nombre

    def desactivar(self) -> None:
        self.activo = False

    def reactivar(self) -> None:
        self.activo = True


@dataclass
class EmpleadoServicio:
    id: UUID
    empleado_id: UUID
    servicio_id: UUID
    activo: bool = True
    created_at: datetime = field(default_factory=_ahora)

    @staticmethod
    def crear(empleado_id: UUID, servicio_id: UUID) -> "EmpleadoServicio":
        return EmpleadoServicio(id=uuid4(), empleado_id=empleado_id, servicio_id=servicio_id)


@dataclass
class HorarioBase:
    """Horario recurrente semanal de un empleado en una sucursal."""
    id: UUID
    empleado_id: UUID
    sucursal_id: UUID
    dia_semana: int          # 0=lunes .. 6=domingo
    hora_inicio: time
    hora_fin: time
    created_at: datetime = field(default_factory=_ahora)

    @staticmethod
    def crear(
        empleado_id: UUID, sucursal_id: UUID, dia_semana: int,
        hora_inicio: time, hora_fin: time,
    ) -> "HorarioBase":
        if not (0 <= dia_semana <= 6):
            raise ValueError("`dia_semana` debe estar entre 0 (lunes) y 6 (domingo)")
        if hora_fin <= hora_inicio:
            raise ValueError("`hora_fin` debe ser posterior a `hora_inicio`")
        return HorarioBase(
            id=uuid4(), empleado_id=empleado_id, sucursal_id=sucursal_id,
            dia_semana=dia_semana, hora_inicio=hora_inicio, hora_fin=hora_fin,
        )


@dataclass
class ExcepcionDisponibilidad:
    """Bloqueo o horario especial puntual de un empleado para una `fecha`."""
    id: UUID
    empleado_id: UUID
    fecha: date
    tipo: TipoExcepcion
    hora_inicio: time | None = None
    hora_fin: time | None = None
    motivo: str | None = None
    created_at: datetime = field(default_factory=_ahora)

    @staticmethod
    def crear(
        empleado_id: UUID, fecha: date, tipo: TipoExcepcion,
        hora_inicio: time | None = None, hora_fin: time | None = None,
        motivo: str | None = None,
    ) -> "ExcepcionDisponibilidad":
        if tipo == TipoExcepcion.HORARIO_ESPECIAL and (hora_inicio is None or hora_fin is None):
            raise ValueError(
                "Un `horario_especial` necesita `hora_inicio` y `hora_fin`."
            )
        if hora_inicio is not None and hora_fin is not None and hora_fin <= hora_inicio:
            raise ValueError("`hora_fin` debe ser posterior a `hora_inicio`")
        return ExcepcionDisponibilidad(
            id=uuid4(), empleado_id=empleado_id, fecha=fecha, tipo=tipo,
            hora_inicio=hora_inicio, hora_fin=hora_fin,
            motivo=(motivo.strip() if motivo and motivo.strip() else None),
        )


@dataclass
class HorarioRecurso:
    """Horario propio de un recurso (ej. cabina en mantenimiento cierta hora).
    Sin filas para un recurso = sin restricción propia."""
    id: UUID
    recurso_id: UUID
    dia_semana: int
    hora_inicio: time
    hora_fin: time
    created_at: datetime = field(default_factory=_ahora)

    @staticmethod
    def crear(
        recurso_id: UUID, dia_semana: int, hora_inicio: time, hora_fin: time,
    ) -> "HorarioRecurso":
        if not (0 <= dia_semana <= 6):
            raise ValueError("`dia_semana` debe estar entre 0 (lunes) y 6 (domingo)")
        if hora_fin <= hora_inicio:
            raise ValueError("`hora_fin` debe ser posterior a `hora_inicio`")
        return HorarioRecurso(
            id=uuid4(), recurso_id=recurso_id, dia_semana=dia_semana,
            hora_inicio=hora_inicio, hora_fin=hora_fin,
        )


# --------------------------------------------------------------------------- #
# Cita
# --------------------------------------------------------------------------- #
@dataclass
class CitaAsignacion:
    """Un intento de oferta a un empleado. Inmutable salvo su `estado` (append,
    nunca se borra): así un rechazo no destruye la cita ni pierde historial."""
    id: UUID
    cita_id: UUID
    empleado_id: UUID
    estado: EstadoAsignacion
    fecha_oferta: datetime = field(default_factory=_ahora)
    fecha_respuesta: datetime | None = None

    @staticmethod
    def ofrecer(cita_id: UUID, empleado_id: UUID) -> "CitaAsignacion":
        return CitaAsignacion(
            id=uuid4(), cita_id=cita_id, empleado_id=empleado_id,
            estado=EstadoAsignacion.OFRECIDA,
        )

    def _exigir_vigente(self) -> None:
        if self.estado != EstadoAsignacion.OFRECIDA:
            raise OfertaNoVigente(
                f"La oferta {self.id} ya está '{self.estado.value}'."
            )

    def aceptar(self) -> None:
        self._exigir_vigente()
        self.estado = EstadoAsignacion.ACEPTADA
        self.fecha_respuesta = _ahora()

    def rechazar(self) -> None:
        self._exigir_vigente()
        self.estado = EstadoAsignacion.RECHAZADA
        self.fecha_respuesta = _ahora()

    def superar(self) -> None:
        """Otro empleado aceptó primero. No es un rechazo del empleado."""
        self._exigir_vigente()
        self.estado = EstadoAsignacion.SUPERADA
        self.fecha_respuesta = _ahora()


@dataclass
class Cita:
    id: UUID
    servicio_id: UUID
    sucursal_id: UUID
    fecha_hora_inicio: datetime
    fecha_hora_fin: datetime
    estado: EstadoCita
    creado_por_usuario_id: UUID
    cliente_id: UUID | None = None
    recurso_id: UUID | None = None
    empleado_id: UUID | None = None       # se llena cuando queda ASIGNADA
    disponibilidad_cruzada: bool = False
    politica_cancelacion_horas: int | None = None
    penalizacion_cancelacion: Decimal | None = None
    motivo_cancelacion: str | None = None
    venta_detalle_id: UUID | None = None
    created_at: datetime = field(default_factory=_ahora)
    asignaciones: list[CitaAsignacion] = field(default_factory=list)

    # Relaciones embebidas opcionales (`?include=`); las puebla el mapper.
    cliente: object | None = field(default=None, compare=False, repr=False)
    empleado: object | None = field(default=None, compare=False, repr=False)

    @staticmethod
    def crear(
        servicio_id: UUID, sucursal_id: UUID, fecha_hora_inicio: datetime,
        fecha_hora_fin: datetime, creado_por_usuario_id: UUID,
        cliente_id: UUID | None = None, recurso_id: UUID | None = None,
        disponibilidad_cruzada: bool = False,
        politica_cancelacion_horas: int | None = None,
        penalizacion_cancelacion: Decimal | None = None,
    ) -> "Cita":
        if fecha_hora_fin <= fecha_hora_inicio:
            raise ValueError("`fecha_hora_fin` debe ser posterior a `fecha_hora_inicio`")
        return Cita(
            id=uuid4(), servicio_id=servicio_id, sucursal_id=sucursal_id,
            fecha_hora_inicio=fecha_hora_inicio, fecha_hora_fin=fecha_hora_fin,
            estado=EstadoCita.POR_ASIGNAR, creado_por_usuario_id=creado_por_usuario_id,
            cliente_id=cliente_id, recurso_id=recurso_id,
            disponibilidad_cruzada=disponibilidad_cruzada,
            politica_cancelacion_horas=politica_cancelacion_horas,
            penalizacion_cancelacion=penalizacion_cancelacion,
        )

    # ------------------------------------------------------------------ #
    def ofertar(self, candidatos: list[UUID]) -> None:
        """Genera una `CitaAsignacion` OFRECIDA por candidato, en paralelo.
        Sin candidatos -> SIN_EMPLEADO_DISPONIBLE (no es un error)."""
        if self.estado not in (EstadoCita.POR_ASIGNAR, EstadoCita.SIN_EMPLEADO_DISPONIBLE):
            raise CitaNoOfertable(
                f"La cita {self.id} está '{self.estado.value}': no se puede reofertar."
            )
        self.asignaciones = [CitaAsignacion.ofrecer(self.id, e) for e in candidatos]
        self.estado = (
            EstadoCita.POR_ASIGNAR if candidatos else EstadoCita.SIN_EMPLEADO_DISPONIBLE
        )

    def _oferta_de(self, empleado_id: UUID) -> CitaAsignacion:
        asign = next(
            (a for a in self.asignaciones
             if a.empleado_id == empleado_id and a.estado == EstadoAsignacion.OFRECIDA),
            None,
        )
        if asign is None:
            raise OfertaNoVigente(
                f"No hay una oferta vigente para el empleado {empleado_id} en esta cita."
            )
        return asign

    def aceptar(self, empleado_id: UUID) -> None:
        asign = self._oferta_de(empleado_id)
        asign.aceptar()
        for otra in self.asignaciones:
            if otra is not asign and otra.estado == EstadoAsignacion.OFRECIDA:
                otra.superar()
        self.empleado_id = empleado_id
        self.estado = EstadoCita.ASIGNADA

    def rechazar(self, empleado_id: UUID) -> None:
        asign = self._oferta_de(empleado_id)
        asign.rechazar()
        if not any(a.estado == EstadoAsignacion.OFRECIDA for a in self.asignaciones):
            self.estado = EstadoCita.SIN_EMPLEADO_DISPONIBLE

    def asignar_manual(self, empleado_id: UUID) -> None:
        """El cajero fuerza el responsable, saltando la cola de oferta."""
        if self.estado in (EstadoCita.COMPLETADA, EstadoCita.CANCELADA, EstadoCita.NO_SHOW):
            raise TransicionCitaInvalida(
                f"No se puede asignar una cita '{self.estado.value}'."
            )
        for a in self.asignaciones:
            if a.estado == EstadoAsignacion.OFRECIDA:
                a.superar()
        self.empleado_id = empleado_id
        self.estado = EstadoCita.ASIGNADA

    # ------------------------------------------------------------------ #
    def iniciar(self) -> None:
        if self.estado != EstadoCita.ASIGNADA:
            raise TransicionCitaInvalida(
                f"Sólo se inicia una cita 'asignada' (está '{self.estado.value}')."
            )
        self.estado = EstadoCita.EN_PROCESO

    def completar(self) -> None:
        if self.estado not in (EstadoCita.ASIGNADA, EstadoCita.EN_PROCESO):
            raise TransicionCitaInvalida(
                f"Sólo se completa una cita 'asignada'/'en_proceso' (está "
                f"'{self.estado.value}')."
            )
        self.estado = EstadoCita.COMPLETADA

    def cancelar(self, motivo: str | None = None) -> None:
        if self.estado in (EstadoCita.COMPLETADA, EstadoCita.CANCELADA):
            raise TransicionCitaInvalida(
                f"La cita {self.id} ya está '{self.estado.value}'."
            )
        self.estado = EstadoCita.CANCELADA
        self.motivo_cancelacion = (motivo.strip() if motivo and motivo.strip() else None)

    def marcar_no_show(self) -> None:
        if self.estado != EstadoCita.ASIGNADA:
            raise TransicionCitaInvalida(
                f"Sólo se marca no-show una cita 'asignada' (está '{self.estado.value}')."
            )
        self.estado = EstadoCita.NO_SHOW

    def vincular_venta(self, venta_detalle_id: UUID) -> None:
        if self.estado != EstadoCita.COMPLETADA:
            raise CitaNoFacturable(
                f"La cita {self.id} no está 'completada' (está '{self.estado.value}')."
            )
        if self.venta_detalle_id is not None:
            raise CitaNoFacturable(f"La cita {self.id} ya fue facturada.")
        self.venta_detalle_id = venta_detalle_id
