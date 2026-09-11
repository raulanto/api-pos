from datetime import date, datetime, time
from decimal import Decimal
from typing import ClassVar, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.agenda.domain.value_objects import EstadoCita, EstadoAsignacion, TipoExcepcion
from app.modules.ventas.infrastructure.api.schemas import PagoRequest
from app.shared.responses import EmbeddableModel
from app.shared.schemas.embeds import ClienteEmbed, UsuarioEmbed

_ORM = ConfigDict(from_attributes=True)


# --------------------------------------------------------------------------- #
# Recurso
# --------------------------------------------------------------------------- #
class RecursoCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nombre: str = Field(min_length=1, max_length=80)
    tipo: Optional[str] = Field(default=None, max_length=30)


class RecursoRenameRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nombre: str = Field(min_length=1, max_length=80)


class RecursoResponse(BaseModel):
    model_config = _ORM
    id: UUID
    sucursal_id: UUID
    nombre: str
    tipo: Optional[str] = None
    activo: bool
    created_at: datetime


# --------------------------------------------------------------------------- #
# empleado_servicio
# --------------------------------------------------------------------------- #
class EmpleadoServicioResponse(BaseModel):
    model_config = _ORM
    id: UUID
    empleado_id: UUID
    servicio_id: UUID
    activo: bool
    created_at: datetime


# --------------------------------------------------------------------------- #
# Disponibilidad
# --------------------------------------------------------------------------- #
class HorarioBaseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sucursal_id: UUID
    dia_semana: int = Field(ge=0, le=6, description="0=lunes .. 6=domingo")
    hora_inicio: time
    hora_fin: time


class HorarioBaseResponse(BaseModel):
    model_config = _ORM
    id: UUID
    empleado_id: UUID
    sucursal_id: UUID
    dia_semana: int
    hora_inicio: time
    hora_fin: time


class ExcepcionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fecha: date
    tipo: TipoExcepcion
    hora_inicio: Optional[time] = None
    hora_fin: Optional[time] = None
    motivo: Optional[str] = Field(default=None, max_length=255)


class ExcepcionResponse(BaseModel):
    model_config = _ORM
    id: UUID
    empleado_id: UUID
    fecha: date
    tipo: TipoExcepcion
    hora_inicio: Optional[time] = None
    hora_fin: Optional[time] = None
    motivo: Optional[str] = None


class HorarioRecursoRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dia_semana: int = Field(ge=0, le=6)
    hora_inicio: time
    hora_fin: time


class HorarioRecursoResponse(BaseModel):
    model_config = _ORM
    id: UUID
    recurso_id: UUID
    dia_semana: int
    hora_inicio: time
    hora_fin: time


# --------------------------------------------------------------------------- #
# Cita
# --------------------------------------------------------------------------- #
class CrearCitaRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    servicio_id: UUID
    fecha_hora_inicio: datetime
    cliente_id: Optional[UUID] = None
    recurso_id: Optional[UUID] = None
    disponibilidad_cruzada: bool = False
    politica_cancelacion_horas: Optional[int] = Field(default=None, gt=0)
    penalizacion_cancelacion: Optional[Decimal] = Field(default=None, ge=0)


class AsignarManualRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    empleado_id: UUID


class CancelarCitaRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    motivo: Optional[str] = Field(default=None, max_length=255)


class FacturarCitaRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    caja_turno_id: UUID
    pagos: List[PagoRequest] = []


class CitaAsignacionResponse(BaseModel):
    model_config = _ORM
    id: UUID
    empleado_id: UUID
    estado: EstadoAsignacion
    fecha_oferta: datetime
    fecha_respuesta: Optional[datetime] = None


class CitaResponse(EmbeddableModel):
    _embed_fields: ClassVar[tuple[str, ...]] = ("cliente", "empleado")
    id: UUID
    servicio_id: UUID
    sucursal_id: UUID
    cliente_id: Optional[UUID] = None
    recurso_id: Optional[UUID] = None
    empleado_id: Optional[UUID] = None
    fecha_hora_inicio: datetime
    fecha_hora_fin: datetime
    estado: EstadoCita
    disponibilidad_cruzada: bool
    politica_cancelacion_horas: Optional[int] = None
    penalizacion_cancelacion: Optional[Decimal] = None
    motivo_cancelacion: Optional[str] = None
    venta_detalle_id: Optional[UUID] = None
    creado_por_usuario_id: UUID
    created_at: datetime
    asignaciones: List[CitaAsignacionResponse] = []
    # Embebidas (?include=cliente,empleado)
    cliente: Optional[ClienteEmbed] = None
    empleado: Optional[UsuarioEmbed] = None
