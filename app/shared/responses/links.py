from fastapi import Request

from app.shared.responses.envelope import Links


def build_links(request: Request, page: int, total_pages: int) -> Links:
    """Construye self/next/prev conservando el resto del query string.

    Solo se reescribe `page`; filtros, `sort` y `page_size` se mantienen.
    """
    total_pages = max(total_pages, 1)

    def url_for(p: int) -> str | None:
        if p < 1 or p > total_pages:
            return None
        return str(request.url.include_query_params(page=p))

    return Links(
        self=str(request.url),
        next=url_for(page + 1) if page < total_pages else None,
        prev=url_for(page - 1) if page > 1 else None,
    )
