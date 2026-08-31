from typing import Callable, Dict, List, Any
from sqlalchemy.ext.asyncio import AsyncSession

class EventBus:
    def __init__(self):
        self._listeners: Dict[str, List[Callable]] = {}

    def suscribir(self, evento: str, listener: Callable) -> None:
        if evento not in self._listeners:
            self._listeners[evento] = []
        self._listeners[evento].append(listener)

    async def publicar(self, evento: str, payload: dict, db: AsyncSession) -> None:
        """
        Publica un evento a todos los listeners registrados.
        Los listeners reciben el payload y la misma sesión de BD para mantener
        la consistencia transaccional (ej: auditoría en el mismo commit).
        """
        for listener in self._listeners.get(evento, []):
            await listener(payload, db)

# Instancia global del bus (útil para inyectar o importar directamente)
event_bus = EventBus()
