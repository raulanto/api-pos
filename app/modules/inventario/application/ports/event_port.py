from abc import ABC, abstractmethod

class EventPort(ABC):
    """Publica eventos de dominio de inventario al bus de eventos de la aplicación.

    El adaptador comparte la misma AsyncSession que el caso de uso, de modo que
    los listeners (p. ej. auditoría) escriben dentro de la misma transacción.
    """

    @abstractmethod
    async def publicar(self, evento: str, payload: dict) -> None: ...
