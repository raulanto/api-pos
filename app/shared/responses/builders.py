from math import ceil
from typing import Any

from fastapi import Request

from app.shared.responses.envelope import ApiResponse, Links, Meta, PageMeta
from app.shared.responses.links import build_links
from app.shared.responses.pagination import Page, PageParams
from app.shared.responses.sorting import Sort


def ok(data: Any, *, meta: Meta | None = None, links: Links | None = None) -> ApiResponse:
    """Sobre para un recurso singular o una lista sin paginación."""
    return ApiResponse(data=data, meta=meta, links=links)


def page_response(
    request: Request,
    page: Page,
    params: PageParams,
    *,
    sort: Sort | str | None = None,
    filters: dict[str, Any] | None = None,
    summary: dict[str, Any] | None = None,
) -> ApiResponse:
    """Sobre para un listado paginado: arma `meta.pagination` + `links`."""
    total_pages = max(ceil(page.total / params.page_size), 1) if page.total else 1
    meta = Meta(
        pagination=PageMeta(
            page=params.page,
            page_size=params.page_size,
            total_items=page.total,
            total_pages=total_pages,
            has_next=params.page < total_pages,
            has_prev=params.page > 1,
        ),
        sort=str(sort) if sort is not None else None,
        filters=filters or None,
        summary=summary or None,
    )
    return ApiResponse(
        data=page.items,
        meta=meta,
        links=build_links(request, params.page, total_pages),
    )
