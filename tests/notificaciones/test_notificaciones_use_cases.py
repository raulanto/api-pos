import pytest
from uuid import uuid4
from datetime import datetime
from app.modules.notificaciones.domain.entities import Notificacion, TipoNotificacion
from app.modules.notificaciones.domain.exceptions import NotificacionNoEncontrada, AccesoDenegadoNotificacion
from app.modules.notificaciones.application.ports.notificacion_repository import NotificacionRepository
from app.modules.notificaciones.application.use_cases.gestionar_notificaciones import (
    NotificacionesUseCase,
    NotificacionFiltrosInput,
)


class InMemoryNotificacionRepository(NotificacionRepository):
    def __init__(self):
        self.items: dict[str, Notificacion] = {}

    async def guardar(self, notificacion: Notificacion) -> Notificacion:
        self.items[str(notificacion.id)] = notificacion
        return notificacion

    async def guardar_varias(self, notificaciones: list[Notificacion]) -> list[Notificacion]:
        for n in notificaciones:
            self.items[str(n.id)] = n
        return notificaciones

    async def obtener_por_id(self, notificacion_id):
        return self.items.get(str(notificacion_id))

    async def listar_por_usuario(self, usuario_id, leida=None, modulo=None, page=1, page_size=20):
        res = [n for n in self.items.values() if n.usuario_id == usuario_id]
        if leida is not None:
            res = [n for n in res if n.leida == leida]
        if modulo:
            res = [n for n in res if n.modulo == modulo]
        return res, len(res)

    async def contar_no_leidas(self, usuario_id):
        return len([n for n in self.items.values() if n.usuario_id == usuario_id and not n.leida])

    async def marcar_todas_como_leidas(self, usuario_id):
        count = 0
        for n in self.items.values():
            if n.usuario_id == usuario_id and not n.leida:
                n.marcar_como_leida()
                count += 1
        return count


@pytest.mark.asyncio
async def test_crear_y_marcar_notificacion_leida():
    repo = InMemoryNotificacionRepository()
    use_case = NotificacionesUseCase(repo)

    user_id = uuid4()
    notif = Notificacion.crear(
        usuario_id=user_id,
        modulo="agenda",
        tipo=TipoNotificacion.OFERTA_CITA,
        titulo="Oferta nueva",
        mensaje="Tienes una cita disponible",
    )
    await repo.guardar(notif)

    assert await use_case.contar_no_leidas(user_id) == 1

    # Listar
    items, total = await use_case.listar(NotificacionFiltrosInput(usuario_id=user_id, leida=False))
    assert total == 1
    assert items[0].id == notif.id

    # Marcar leída
    actualizada = await use_case.marcar_como_leida(notif.id, user_id)
    assert actualizada.leida is True
    assert actualizada.fecha_leida is not None
    assert await use_case.contar_no_leidas(user_id) == 0


@pytest.mark.asyncio
async def test_marcar_todas_como_leidas():
    repo = InMemoryNotificacionRepository()
    use_case = NotificacionesUseCase(repo)

    user_id = uuid4()
    n1 = Notificacion.crear(user_id, "agenda", TipoNotificacion.OFERTA_CITA, "T1", "M1")
    n2 = Notificacion.crear(user_id, "agenda", TipoNotificacion.CITA_ASIGNADA, "T2", "M2")
    await repo.guardar_varias([n1, n2])

    assert await use_case.contar_no_leidas(user_id) == 2

    count = await use_case.marcar_todas_como_leidas(user_id)
    assert count == 2
    assert await use_case.contar_no_leidas(user_id) == 0
