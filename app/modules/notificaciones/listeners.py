import logging
from typing import Any
from uuid import UUID
from app.shared.events import event_bus
from app.modules.notificaciones.domain.entities import Notificacion, TipoNotificacion
from app.modules.notificaciones.infrastructure.persistence.notificacion_repository_impl import NotificacionRepositoryImpl

logger = logging.getLogger("notificaciones.listeners")


async def procesar_evento_notificacion(payload: dict, db: Any = None) -> None:
    """
    Listener que convierte eventos de dominio (principalmente del módulo Agenda/Citas)
    en registros persistentes de Notificacion en BD.
    """
    if db is None:
        return

    accion = payload.get("accion")
    modulo = payload.get("modulo", "agenda")
    entidad = payload.get("entidad")
    entidad_id = payload.get("entidad_id")
    detalle = payload.get("detalle") or {}
    sucursal_id_raw = payload.get("sucursal_id")
    sucursal_id = UUID(str(sucursal_id_raw)) if sucursal_id_raw else None

    repo = NotificacionRepositoryImpl(db)
    notificaciones_a_crear: list[Notificacion] = []

    # 1. CitaCreada (con ofertas a empleados)
    if accion == "CitaCreada":
        ofertas = detalle.get("ofertas") or []
        servicio_nombre = detalle.get("servicio_nombre", "Servicio")
        fecha_hora = detalle.get("fecha_hora", "")

        for oferta in ofertas:
            emp_id_raw = oferta.get("empleado_id") if isinstance(oferta, dict) else getattr(oferta, "empleado_id", None)
            if emp_id_raw:
                try:
                    emp_id = UUID(str(emp_id_raw))
                    notif = Notificacion.crear(
                        usuario_id=emp_id,
                        modulo="agenda",
                        tipo=TipoNotificacion.OFERTA_CITA,
                        titulo="Nueva oferta de cita disponible",
                        mensaje=f"Se te ha ofertado una cita para {servicio_nombre} ({fecha_hora}).",
                        sucursal_id=sucursal_id,
                        entidad=entidad,
                        entidad_id=str(entidad_id),
                        datos={"detalle": detalle},
                    )
                    notificaciones_a_crear.append(notif)
                except Exception as e:
                    logger.warning(f"Error procesar usuario_id oferta: {e}")

    # 2. CitaOfertaAceptada / CitaAsignada
    elif accion in ("CitaOfertaAceptada", "CitaAsignada"):
        empleado_id_raw = detalle.get("empleado_id")
        cliente_nombre = detalle.get("cliente_nombre", "Cliente")
        if empleado_id_raw:
            try:
                emp_id = UUID(str(empleado_id_raw))
                notif = Notificacion.crear(
                    usuario_id=emp_id,
                    modulo="agenda",
                    tipo=TipoNotificacion.CITA_ASIGNADA,
                    titulo="Cita asignada confirmada",
                    mensaje=f"Tienes una cita asignada con {cliente_nombre}.",
                    sucursal_id=sucursal_id,
                    entidad=entidad,
                    entidad_id=str(entidad_id),
                    datos={"detalle": detalle},
                )
                notificaciones_a_crear.append(notif)
            except Exception as e:
                logger.warning(f"Error procesar cita asignada: {e}")

    # 3. CitaEstadoActualizado / CitaCancelada / CitaReagendada
    elif accion in ("CitaEstadoActualizado", "CitaCancelada", "CitaReagendada"):
        empleado_id_raw = detalle.get("empleado_id")
        estado_nuevo = detalle.get("nuevo_estado", accion)
        if empleado_id_raw:
            try:
                emp_id = UUID(str(empleado_id_raw))
                tipo_notif = (
                    TipoNotificacion.CITA_CANCELADA
                    if accion == "CitaCancelada"
                    else TipoNotificacion.CITA_ESTADO_CAMBIADO
                )
                notif = Notificacion.crear(
                    usuario_id=emp_id,
                    modulo="agenda",
                    tipo=tipo_notif,
                    titulo=f"Cita {estado_nuevo.replace('_', ' ').capitalize()}",
                    mensaje=f"La cita {entidad_id} ha cambiado a estado: {estado_nuevo}.",
                    sucursal_id=sucursal_id,
                    entidad=entidad,
                    entidad_id=str(entidad_id),
                    datos={"detalle": detalle},
                )
                notificaciones_a_crear.append(notif)
            except Exception as e:
                logger.warning(f"Error procesar cambio cita: {e}")

    # 4. CajaTurnoAbierto
    elif accion == "CajaTurnoAbierto":
        usr_id_raw = payload.get("usuario_id")
        saldo_inicial = detalle.get("saldo_inicial", "0")
        if usr_id_raw:
            try:
                usr_id = UUID(str(usr_id_raw))
                notif = Notificacion.crear(
                    usuario_id=usr_id,
                    modulo="ventas",
                    tipo=TipoNotificacion.CAJA_ABIERTA,
                    titulo="Turno de caja abierto",
                    mensaje=f"Se ha abierto el turno de caja con saldo inicial de ${saldo_inicial}.",
                    sucursal_id=sucursal_id,
                    entidad=entidad,
                    entidad_id=str(entidad_id) if entidad_id else None,
                    datos={"detalle": detalle},
                )
                notificaciones_a_crear.append(notif)
            except Exception as e:
                logger.warning(f"Error procesar apertura caja: {e}")

    # 5. CajaTurnoCerrado
    elif accion == "CajaTurnoCerrado":
        usr_id_raw = payload.get("usuario_id")
        saldo_final = detalle.get("saldo_final_declarado", "0")
        if usr_id_raw:
            try:
                usr_id = UUID(str(usr_id_raw))
                notif = Notificacion.crear(
                    usuario_id=usr_id,
                    modulo="ventas",
                    tipo=TipoNotificacion.CAJA_CERRADA,
                    titulo="Turno de caja cerrado",
                    mensaje=f"Se ha cerrado el turno de caja. Saldo final declarado: ${saldo_final}.",
                    sucursal_id=sucursal_id,
                    entidad=entidad,
                    entidad_id=str(entidad_id) if entidad_id else None,
                    datos={"detalle": detalle},
                )
                notificaciones_a_crear.append(notif)
            except Exception as e:
                logger.warning(f"Error procesar cierre caja: {e}")

    # 6. UsuarioSesionIniciada
    elif accion == "UsuarioSesionIniciada":
        usr_id_raw = payload.get("usuario_id")
        ip = detalle.get("ip", "")
        if usr_id_raw:
            try:
                usr_id = UUID(str(usr_id_raw))
                notif = Notificacion.crear(
                    usuario_id=usr_id,
                    modulo="usuarios",
                    tipo=TipoNotificacion.USUARIO_LOGIN,
                    titulo="Inicio de sesión exitoso",
                    mensaje=f"Has iniciado sesión en el sistema{f' (IP {ip})' if ip else ''}.",
                    sucursal_id=sucursal_id,
                    entidad="Usuario",
                    entidad_id=str(usr_id),
                    datos={"detalle": detalle},
                )
                notificaciones_a_crear.append(notif)
            except Exception as e:
                logger.warning(f"Error procesar inicio sesion: {e}")

    # 7. UsuarioSesionCerrada
    elif accion == "UsuarioSesionCerrada":
        usr_id_raw = payload.get("usuario_id")
        if usr_id_raw:
            try:
                usr_id = UUID(str(usr_id_raw))
                notif = Notificacion.crear(
                    usuario_id=usr_id,
                    modulo="usuarios",
                    tipo=TipoNotificacion.USUARIO_LOGOUT,
                    titulo="Cierre de sesión",
                    mensaje="Has cerrado sesión correctamente del sistema.",
                    sucursal_id=sucursal_id,
                    entidad="Usuario",
                    entidad_id=str(usr_id),
                    datos={"detalle": detalle},
                )
                notificaciones_a_crear.append(notif)
            except Exception as e:
                logger.warning(f"Error procesar cierre sesion: {e}")

    if notificaciones_a_crear:
        creadas = await repo.guardar_varias(notificaciones_a_crear)
        from app.core.signals import signal_manager
        for n in creadas:
            await signal_manager.emitir_modulo(
                modulo="notificaciones",
                evento="NuevaNotificacion",
                payload={
                    "id": str(n.id),
                    "usuario_id": str(n.usuario_id),
                    "modulo": n.modulo,
                    "tipo": n.tipo,
                    "titulo": n.titulo,
                    "mensaje": n.mensaje,
                    "leida": n.leida,
                    "created_at": n.created_at.isoformat() if n.created_at else "",
                    "datos": n.datos,
                },
            )


def registrar_listeners_notificaciones():
    eventos = [
        "CitaCreada",
        "CitaAsignada",
        "CitaOfertaAceptada",
        "CitaOfertaRechazada",
        "CitaEstadoActualizado",
        "CitaCancelada",
        "CitaReagendada",
        "CajaTurnoAbierto",
        "CajaTurnoCerrado",
        "UsuarioSesionIniciada",
        "UsuarioSesionCerrada",
    ]
    for evento in eventos:
        event_bus.suscribir(evento, procesar_evento_notificacion)
