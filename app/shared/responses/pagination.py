from dataclasses import dataclass, field
from typing import Generic, TypeVar

from fastapi import Query

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100

T = TypeVar("T")


@dataclass
class PageParams:
    """Parámetros de paginación basada en página (1-indexada).

    Expone `limit`/`offset` para los repositorios, que siguen trabajando con
    ventana deslizante.
    """
    page: int = 1
    page_size: int = DEFAULT_PAGE_SIZE

    def __post_init__(self) -> None:
        self.page = max(1, self.page)
        self.page_size = max(1, min(self.page_size, MAX_PAGE_SIZE))

    @property
    def limit(self) -> int:
        return self.page_size

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


def page_params(
    page: int = Query(1, ge=1, description="Número de página (1-indexada)"),
    page_size: int = Query(
        DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE, description="Tamaño de página"
    ),
) -> PageParams:
    return PageParams(page=page, page_size=page_size)


@dataclass
class Page(Generic[T]):
    """Resultado de un listado en la capa de aplicación: ítems de la página + total global."""
    items: list[T] = field(default_factory=list)
    total: int = 0
