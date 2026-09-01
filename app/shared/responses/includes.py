from typing import Callable

from fastapi import HTTPException, Query


def make_include_dependency(allowed: set[str]) -> Callable[..., frozenset[str]]:
    """Crea una dependencia que parsea `?include=rel1,rel2`.

    `allowed` es la whitelist POR ENDPOINT. Si se pide una relación fuera de la
    lista → 422. Devuelve un `frozenset` (vacío si no se pidió nada).

    El repositorio usa el frozenset para decidir qué `selectinload(...)` aplicar
    (evita el N+1) y el mapper para poblar sólo esas relaciones en la entidad.
    """
    disponibles = ", ".join(sorted(allowed)) or "(ninguna)"

    def _dep(
        include: str | None = Query(
            default=None,
            description=f"Relaciones a embeber, separadas por coma. Disponibles: {disponibles}",
        ),
    ) -> frozenset[str]:
        if not include:
            return frozenset()
        pedidas = {p.strip() for p in include.split(",") if p.strip()}
        desconocidas = pedidas - allowed
        if desconocidas:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"include no soportado: {', '.join(sorted(desconocidas))}. "
                    f"Disponibles: {disponibles}"
                ),
            )
        return frozenset(pedidas)

    return _dep
