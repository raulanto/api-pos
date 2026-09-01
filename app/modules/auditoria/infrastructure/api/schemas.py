from datetime import datetime
from typing import Any, ClassVar, Optional
from uuid import UUID

from app.shared.responses import EmbeddableModel
from app.shared.schemas.embeds import UsuarioEmbed


class LogAuditoriaResponse(EmbeddableModel):
    _embed_fields: ClassVar[tuple[str, ...]] = ("usuario",)
    id: UUID
    usuario_id: UUID
    modulo: str
    accion: str
    entidad: str
    entidad_id: str
    detalle: Optional[Any] = None
    ip_address: Optional[str] = None
    fecha: datetime
    # Embebida (?include=usuario)
    usuario: Optional[UsuarioEmbed] = None
