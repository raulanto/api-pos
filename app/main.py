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
app.include_router(usuarios_router, prefix="/api/v1/usuarios", tags=["usuarios"])

@app.get("/health")
def health_check():
    return {"status": "ok"}
