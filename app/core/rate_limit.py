"""Rate limiting simple en memoria para el login (sección 12 del plan).

Ventana deslizante por clave (ip:email). Suficiente para el MVP y para un solo
proceso; si se escala a varios workers conviene mover el contador a Redis.
"""
import time
from collections import defaultdict, deque

from fastapi import HTTPException, status

from app.core.config import settings


class InMemoryRateLimiter:
    def __init__(self, max_intentos: int, ventana_segundos: int):
        self._max = max_intentos
        self._ventana = ventana_segundos
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def check(self, clave: str) -> None:
        ahora = time.monotonic()
        limite = ahora - self._ventana
        cola = self._hits[clave]

        while cola and cola[0] < limite:
            cola.popleft()

        if len(cola) >= self._max:
            reintento = int(self._ventana - (ahora - cola[0])) + 1
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Demasiados intentos de inicio de sesión. Probá de nuevo más tarde.",
                headers={"Retry-After": str(max(reintento, 1))},
            )

        cola.append(ahora)

    def reset(self, clave: str | None = None) -> None:
        if clave is None:
            self._hits.clear()
        else:
            self._hits.pop(clave, None)


login_rate_limiter = InMemoryRateLimiter(
    max_intentos=settings.login_rate_limit_max,
    ventana_segundos=settings.login_rate_limit_window_seconds,
)
