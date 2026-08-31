from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, model_serializer

T = TypeVar("T")


class PageMeta(BaseModel):
    """Metadatos de paginación derivados (page/page_size son la fuente de verdad)."""
    page: int
    page_size: int
    total_items: int
    total_pages: int
    has_next: bool
    has_prev: bool


class Meta(BaseModel):
    pagination: Optional[PageMeta] = None
    sort: Optional[str] = None
    filters: Optional[dict[str, Any]] = None
    # Espacio para agregados propios de un endpoint (p. ej. totales en reportes).
    summary: Optional[dict[str, Any]] = None

    @model_serializer(mode="wrap")
    def _drop_none(self, handler):
        return {k: v for k, v in handler(self).items() if v is not None}


class Links(BaseModel):
    # next/prev pueden ser null legítimamente (bordes de la paginación): se
    # conservan como null para que el cliente no tenga que adivinar.
    self: Optional[str] = None
    next: Optional[str] = None
    prev: Optional[str] = None


class ApiResponse(BaseModel, Generic[T]):
    """Sobre de éxito. `data` puede ser un objeto o una lista.

    En recursos singulares `meta`/`links` se omiten de la salida (van en None);
    `data` se serializa completo, incluidos sus campos nullables.
    """
    model_config = ConfigDict(from_attributes=True)

    success: bool = True
    data: T
    meta: Optional[Meta] = None
    links: Optional[Links] = None

    @model_serializer(mode="wrap")
    def _omit_empty_envelope(self, handler):
        out = handler(self)
        if out.get("meta") is None:
            out.pop("meta", None)
        if out.get("links") is None:
            out.pop("links", None)
        return out


class ErrorDetail(BaseModel):
    code: str
    message: str
    fields: Optional[dict[str, list[str]]] = None


class ErrorResponse(BaseModel):
    success: bool = False
    error: ErrorDetail
