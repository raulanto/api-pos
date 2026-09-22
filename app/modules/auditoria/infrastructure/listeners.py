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
# Ventas
event_bus.suscribir("VentaCreada", registrar_auditoria)
event_bus.suscribir("VentaAnulada", registrar_auditoria)
event_bus.suscribir("DescuentoManualAplicado", registrar_auditoria)

# Caja
event_bus.suscribir("CajaTurnoAbierto", registrar_auditoria)
event_bus.suscribir("CajaTurnoCerrado", registrar_auditoria)
event_bus.suscribir("MovimientoCajaRegistrado", registrar_auditoria)
event_bus.suscribir("TurnoConciliado", registrar_auditoria)

# Inventario
event_bus.suscribir("MovimientoInventarioRegistrado", registrar_auditoria)
event_bus.suscribir("TransferenciaInventarioRegistrada", registrar_auditoria)
event_bus.suscribir("ProductoCreado", registrar_auditoria)
event_bus.suscribir("ProductoEditado", registrar_auditoria)
event_bus.suscribir("ProductoDesactivado", registrar_auditoria)
event_bus.suscribir("CategoriaCreada", registrar_auditoria)
event_bus.suscribir("CategoriaEditada", registrar_auditoria)

# Usuarios
event_bus.suscribir("UsuarioCreado", registrar_auditoria)
event_bus.suscribir("UsuarioEditado", registrar_auditoria)
event_bus.suscribir("UsuarioDesactivado", registrar_auditoria)
event_bus.suscribir("UsuarioReactivado", registrar_auditoria)

# Clientes
event_bus.suscribir("ClienteCreado", registrar_auditoria)
event_bus.suscribir("ClienteEditado", registrar_auditoria)

# Proveedores
event_bus.suscribir("ProveedorCreado", registrar_auditoria)
event_bus.suscribir("ProveedorEditado", registrar_auditoria)

# Promociones
event_bus.suscribir("PromocionCreada", registrar_auditoria)
event_bus.suscribir("PromocionEditada", registrar_auditoria)

# Sucursales
event_bus.suscribir("SucursalCreada", registrar_auditoria)
event_bus.suscribir("SucursalEditada", registrar_auditoria)
