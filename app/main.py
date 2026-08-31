from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings

app = FastAPI(
    title="POS Backend API",
    version="1.0.0",
)

# CORS Config
origins = [origin.strip() for origin in settings.cors_origins.split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.modules.usuarios.infrastructure.api.router import router as usuarios_router
from app.modules.inventario.infrastructure.api.router import router as inventario_router
from app.modules.clientes.infrastructure.api.router import router as clientes_router
from app.modules.ventas.infrastructure.api.router import router as ventas_router

app.include_router(usuarios_router, prefix="/api/v1/usuarios", tags=["usuarios"])
app.include_router(inventario_router, prefix="/api/v1/inventario", tags=["inventario"])
app.include_router(clientes_router, prefix="/api/v1/clientes", tags=["clientes"])
app.include_router(ventas_router, prefix="/api/v1/ventas", tags=["ventas"])

@app.get("/health")
def health_check():
    return {"status": "ok"}
