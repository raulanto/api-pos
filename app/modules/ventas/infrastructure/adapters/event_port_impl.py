from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.ventas.application.ports.event_port import EventPort
from app.shared.events import event_bus

class EventPortImpl(EventPort):
    def __init__(self, db: AsyncSession):
        self._db = db

    async def publicar(self, evento: str, payload: dict) -> None:
        await event_bus.publicar(evento, payload, self._db)
