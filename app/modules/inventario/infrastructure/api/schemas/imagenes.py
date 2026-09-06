from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class AgregarImagenRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: HttpUrl
    alt_texto: Optional[str] = Field(default=None, max_length=255)
    orden: int = Field(default=0, ge=0)
    es_principal: bool = False


class ActualizarImagenRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: Optional[HttpUrl] = None
    alt_texto: Optional[str] = Field(default=None, max_length=255)
    cambiar_alt_texto: bool = False
    orden: Optional[int] = Field(default=None, ge=0)
    es_principal: Optional[bool] = None


class ImagenResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    producto_id: Optional[UUID] = None
    producto_unidad_id: Optional[UUID] = None
    # `url`: la externa tal cual, o una URL GET prefirmada si la imagen vive en S3.
    url: Optional[str] = None
    # `thumbnail_url`: prefirmada de la miniatura (sólo imágenes S3). Puede dar
    # 404 unos segundos hasta que la Lambda termina de generarla.
    thumbnail_url: Optional[str] = None
    object_key: Optional[str] = None
    alt_texto: Optional[str] = None
    orden: int
    es_principal: bool
