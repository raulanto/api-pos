from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.inventario.application.ports.event_port import EventPort
from app.shared.events import event_bus


"""
    Adaptador para la publicación de eventos.

    @param db: Sesión de la base de datos.
    @return: Instancia de la clase EventPortImpl.
    """
class EventPortImpl(EventPort):
    def __init__(self, db: AsyncSession):
        self._db = db

    """
        Publica un evento en el sistema.

        @param evento: Evento a publicar.
        @param payload: Payload del evento.
        @return: None
    """
    async def publicar(self, evento: str, payload: dict) -> None:
        await event_bus.publicar(evento, payload, self._db)
