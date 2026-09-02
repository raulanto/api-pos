from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.shared.exceptions import register_exception_handlers

app = FastAPI(
    title="POS Backend API",
    version="1.0.0",
)

# Contrato único de errores: todo error sale como {success:false, error:{...}}.
register_exception_handlers(app)

# CORS Config
origins = [origin.strip() for origin in settings.cors_origins.split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registra los listeners de auditoría en el event_bus global (efecto de import).
from app.modules.auditoria.infrastructure import listeners as _auditoria_listeners  # noqa: F401,E402

from app.modules.usuarios.infrastructure.api.router import router as usuarios_router
from app.modules.usuarios.infrastructure.api.roles_router import router as roles_router, permisos_router
from app.modules.usuarios.infrastructure.api.sucursales_router import router as sucursales_router
from app.modules.inventario.infrastructure.api.router import router as inventario_router
from app.modules.clientes.infrastructure.api.router import router as clientes_router
from app.modules.ventas.infrastructure.api.router import router as ventas_router, caja_router
from app.modules.reportes.infrastructure.api.router import router as reportes_router
from app.modules.auditoria.infrastructure.api.router import router as auditoria_router

app.include_router(usuarios_router, prefix="/api/v1/usuarios", tags=["usuarios"])
app.include_router(roles_router, prefix="/api/v1/roles", tags=["roles"])
app.include_router(permisos_router, prefix="/api/v1/permisos", tags=["permisos"])
app.include_router(sucursales_router, prefix="/api/v1/sucursales", tags=["sucursales"])
app.include_router(inventario_router, prefix="/api/v1/inventario", tags=["inventario"])
app.include_router(clientes_router, prefix="/api/v1/clientes", tags=["clientes"])
app.include_router(ventas_router, prefix="/api/v1/ventas", tags=["ventas"])
app.include_router(caja_router, prefix="/api/v1/caja-turnos", tags=["caja"])
app.include_router(reportes_router, prefix="/api/v1/reportes", tags=["reportes"])
app.include_router(auditoria_router, prefix="/api/v1/auditoria", tags=["auditoria"])

@app.get("/health")
def health_check():
    return {"status": "ok"}
