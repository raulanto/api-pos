from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4
from enum import Enum


class TipoNotificacion(str, Enum):
    OFERTA_CITA = "oferta_cita"
    CITA_ASIGNADA = "cita_asignada"
    CITA_CANCELADA = "cita_cancelada"
    CITA_REAGENDADA = "cita_reagendada"
    CITA_ESTADO_CAMBIADO = "cita_estado_cambiado"
    SISTEMA = "sistema"


@dataclass
class Notificacion:
    id: UUID
    usuario_id: UUID
    modulo: str
    tipo: str
    titulo: str
    mensaje: str
    leida: bool = False
    fecha_leida: datetime | None = None
    sucursal_id: UUID | None = None
    entidad: str | None = None
    entidad_id: str | None = None
    datos: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)

    @staticmethod
    def crear(
        usuario_id: UUID,
        modulo: str,
        tipo: str,
        titulo: str,
        mensaje: str,
        sucursal_id: UUID | None = None,
        entidad: str | None = None,
        entidad_id: str | None = None,
        datos: dict | None = None,
    ) -> "Notificacion":
        return Notificacion(
            id=uuid4(),
            usuario_id=usuario_id,
            modulo=modulo,
            tipo=tipo,
            titulo=titulo,
            mensaje=mensaje,
            leida=False,
            fecha_leida=None,
            sucursal_id=sucursal_id,
            entidad=entidad,
            entidad_id=str(entidad_id) if entidad_id else None,
            datos=datos or {},
            created_at=datetime.utcnow(),
        )

    def marcar_como_leida(self) -> None:
        if not self.leida:
            self.leida = True
            self.fecha_leida = datetime.utcnow()
