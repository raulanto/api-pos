"""Contrato único de respuestas HTTP de la API.

Sobre de éxito:  {success, data, meta?, links?}
Sobre de error:  {success: false, error: {code, message, fields?}}

Nomenclatura: snake_case en inglés (page, page_size, total_items, total_pages,
has_next, has_prev). Los módulos NO arman el sobre: devuelven entidades de
dominio o un `Page`; el router usa `ok()` / `page_response()`.
"""
from app.shared.responses.envelope import (
    ApiResponse, Meta, PageMeta, Links, ErrorDetail, ErrorResponse,
)
from app.shared.responses.pagination import (
    Page, PageParams, page_params, DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE,
)
from app.shared.responses.sorting import Sort, make_sort_dependency
from app.shared.responses.builders import ok, page_response
from app.shared.responses.routing import EnvelopeRoute

__all__ = [
    "ApiResponse", "Meta", "PageMeta", "Links", "ErrorDetail", "ErrorResponse",
    "Page", "PageParams", "page_params", "DEFAULT_PAGE_SIZE", "MAX_PAGE_SIZE",
    "Sort", "make_sort_dependency",
    "ok", "page_response", "EnvelopeRoute",
]
