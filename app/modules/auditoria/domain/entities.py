from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4
from typing import Optional

"""
    Entidad: LogAuditoria
    Descripcion: Entidad que representa los logs de auditoria.
    Atributos:
    - id: ID del log.
    - usuario_id: ID del usuario.
    - modulo: Modulo.
    - accion: Accion.
    - entidad: Entidad.
    - entidad_id: ID de la entidad.
    - detalle: Detalle.
    - ip_address: Direccion IP.
    - fecha: Fecha.
"""
@dataclass
class LogAuditoria:
    id: UUID
    usuario_id: UUID
    modulo: str
    accion: str
    entidad: str
    entidad_id: str
    detalle: Optional[str]
    ip_address: Optional[str]
    fecha: datetime = field(default_factory=datetime.utcnow)

    """
        Método estático para crear un nuevo log de auditoria.
        Parámetros:
        - usuario_id: ID del usuario.
        - modulo: Modulo.
        - accion: Accion.
        - entidad: Entidad.
        - entidad_id: ID de la entidad.
        - detalle: Detalle.
        - ip_address: Direccion IP.
        Retorna:
        - LogAuditoria: Nuevo log de auditoria.
    """
    @staticmethod
    def crear(
        usuario_id: UUID, modulo: str, accion: str, 
        entidad: str, entidad_id: str, detalle: Optional[str] = None, 
        ip_address: Optional[str] = None
    ) -> "LogAuditoria":
        return LogAuditoria(
            id=uuid4(),
            usuario_id=usuario_id,
            modulo=modulo,
            accion=accion,
            entidad=entidad,
            entidad_id=entidad_id,
            detalle=detalle,
            ip_address=ip_address
        )
