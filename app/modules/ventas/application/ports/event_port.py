from abc import ABC, abstractmethod

class EventPort(ABC):
    @abstractmethod
    async def publicar(self, evento: str, payload: dict) -> None: ...
