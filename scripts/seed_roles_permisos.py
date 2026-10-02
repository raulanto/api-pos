import asyncio
import uuid
import logging
from sqlalchemy import select, text
from app.core.database import AsyncSessionLocal

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("seed_roles_permisos")

ROLES = [
    ("admin", "Administrador", "Acceso total al sistema"),
    ("gerente", "Gerente", "Gestión operativa de sucursal(es)"),
    ("cajero", "Cajero", "Registro de ventas en punto de venta"),
    ("almacenista", "Almacenista", "Gestión de inventario y stock"),
    ("empleado", "Empleado", "Atiende servicios agendados; ve y responde sus propias citas"),
]

PERMISOS = [
    # Usuarios y Roles
    ("usuarios.crear", "Crear usuarios"),
    ("usuarios.leer", "Ver/listar usuarios"),
    ("usuarios.editar", "Editar datos de usuario"),
    ("usuarios.desactivar", "Dar de baja a un usuario"),
    ("roles.gestionar", "Crear/editar roles y asignar permisos"),
    
    # Inventario
    ("inventario.crear", "Crear productos/categorías"),
    ("inventario.editar", "Editar productos/categorías"),
    ("inventario.leer", "Consultar productos, categorías, existencias"),
    ("inventario.movimiento", "Registrar entradas/salidas de stock"),
    ("inventario.eliminar", "Eliminar productos de catálogo"),
    
    # Clientes
    ("clientes.crear", "Crear clientes"),
    ("clientes.leer", "Ver/listar clientes"),
    ("clientes.editar", "Editar clientes"),
    ("clientes.eliminar", "Eliminar/desactivar clientes"),
    
    # Ventas y Caja
    ("ventas.crear", "Registrar una venta"),
    ("ventas.leer", "Ver/listar ventas"),
    ("ventas.anular", "Cancelar/anular una venta"),
    ("caja.abrir", "Abrir turno de caja"),
    ("caja.cerrar", "Cerrar turno de caja"),
    ("caja.conciliar", "Conciliar diferencias de caja"),
    
    # Agenda / Citas
    ("agenda.administrar", "Alta/baja de recursos, horarios y calificación de empleados"),
    ("citas.gestionar", "Crear, reasignar, cancelar y facturar cualquier cita"),
    ("citas.ver_propias", "Ver las citas propias (ofertadas o asignadas)"),
    ("citas.responder_oferta", "Aceptar o rechazar una oferta de cita propia"),
    
    # Reportes y Auditoría
    ("reportes.leer", "Consultar reportes"),
    ("reportes.exportar", "Exportar reportes a Excel/PDF"),
    ("auditoria.leer", "Consultar el log de auditoría"),
]

ASIGNACIONES = {
    "gerente": [
        "inventario.crear", "inventario.editar", "inventario.leer", "inventario.movimiento",
        "clientes.crear", "clientes.leer", "clientes.editar", "clientes.eliminar",
        "ventas.crear", "ventas.leer", "ventas.anular", "caja.abrir", "caja.cerrar",
        "agenda.administrar", "citas.gestionar", "citas.ver_propias", "citas.responder_oferta",
        "reportes.leer", "reportes.exportar", "usuarios.leer",
    ],
    "cajero": [
        "ventas.crear", "ventas.leer", "caja.abrir", "caja.cerrar",
        "clientes.crear", "clientes.leer", "inventario.leer",
        "citas.gestionar", "citas.ver_propias", "citas.responder_oferta",
    ],
    "almacenista": [
        "inventario.crear", "inventario.editar", "inventario.leer", "inventario.movimiento",
    ],
    "empleado": [
        "citas.ver_propias", "citas.responder_oferta", "inventario.leer",
    ],
}


async def run_seed():
    async with AsyncSessionLocal() as session:
        logger.info("Iniciando seed de roles y permisos...")

        # 1. Insertar Permisos
        for codigo, desc in PERMISOS:
            await session.execute(
                text(
                    "INSERT INTO permiso (id, codigo, descripcion) "
                    "VALUES (:id, :c, :d) ON CONFLICT (codigo) DO UPDATE SET descripcion = EXCLUDED.descripcion"
                ),
                {"id": str(uuid.uuid4()), "c": codigo, "d": desc},
            )

        # 2. Insertar Roles
        for codigo, nombre, desc in ROLES:
            await session.execute(
                text(
                    "INSERT INTO rol (id, codigo, nombre, descripcion) "
                    "VALUES (:id, :c, :n, :d) ON CONFLICT (codigo) DO UPDATE SET nombre = EXCLUDED.nombre, descripcion = EXCLUDED.descripcion"
                ),
                {"id": str(uuid.uuid4()), "c": codigo, "n": nombre, "d": desc},
            )

        # 3. Asignar todos los permisos al rol ADMIN
        await session.execute(
            text(
                "INSERT INTO rol_permiso (rol_id, permiso_id) "
                "SELECT r.id, p.id FROM rol r CROSS JOIN permiso p "
                "WHERE r.codigo = 'admin' "
                "ON CONFLICT DO NOTHING"
            )
        )

        # 4. Asignar permisos específicos a roles (gerente, cajero, almacenista, empleado)
        for rol_codigo, permisos in ASIGNACIONES.items():
            for permiso_codigo in permisos:
                await session.execute(
                    text(
                        "INSERT INTO rol_permiso (rol_id, permiso_id) "
                        "SELECT r.id, p.id FROM rol r, permiso p "
                        "WHERE r.codigo = :rc AND p.codigo = :pc "
                        "ON CONFLICT DO NOTHING"
                    ),
                    {"rc": rol_codigo, "pc": permiso_codigo},
                )

        await session.commit()
        logger.info("¡Seed de roles y permisos completado exitosamente con idempotencia!")


if __name__ == "__main__":
    asyncio.run(run_seed())
