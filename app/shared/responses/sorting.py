from dataclasses import dataclass
from typing import Callable

from fastapi import HTTPException, Query, status


@dataclass(frozen=True)
class Sort:
    field: str
    direction: str  # "asc" | "desc"

    def __str__(self) -> str:
        return f"{self.field}:{self.direction}"

    @property
    def descending(self) -> bool:
        return self.direction == "desc"


def make_sort_dependency(
    allowed_fields: set[str], default: str = "created_at:desc"
) -> Callable[..., Sort]:
    """Crea una dependencia FastAPI que parsea `?sort=campo:dir`.

    `allowed_fields` es la whitelist POR ENDPOINT: nunca llega al SQL un nombre
    de columna arbitrario. El repositorio mapea el nombre lógico a su columna.
    """
    ejemplo = ", ".join(sorted(allowed_fields)) or "created_at"

    def _dep(
        sort: str = Query(
            default,
            description=f"Orden `campo:asc|desc`. Campos: {ejemplo}",
        ),
    ) -> Sort:
        field, _, direction = sort.partition(":")
        direction = (direction or "asc").lower()
        if field not in allowed_fields or direction not in ("asc", "desc"):
            raise HTTPException(
                status_code=422,
                detail=f"Parámetro sort inválido: '{sort}'. Campos permitidos: {ejemplo}",
            )
        return Sort(field=field, direction=direction)

    return _dep
