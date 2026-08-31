from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.auditoria.infrastructure.persistence.orm_models import LogAuditoriaORM
from app.shared.events import event_bus

async def registrar_auditoria(payload: dict, db: AsyncSession) -> None:
    """
    Listener que se suscribe a los eventos y guarda la auditoría en la BD.
    Utiliza la misma AsyncSession (db) que el publicador para mantenerse 
    en la misma transacción (commit conjunto).
    """
    log = LogAuditoriaORM(
        usuario_id=payload.get("usuario_id"),
        modulo=payload.get("modulo"),
        accion=payload.get("accion"),
        entidad=payload.get("entidad"),
        entidad_id=str(payload.get("entidad_id")),
        detalle=payload.get("detalle")
    )
    db.add(log)
    # No se hace db.commit() aquí para asegurar consistencia transaccional

# Suscribir los handlers al event_bus global
event_bus.suscribir("VentaCreada", registrar_auditoria)
