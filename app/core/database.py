from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.core.config import settings

engine = create_async_engine(
    settings.database_url,
    echo=(settings.entorno == "development"),
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Unidad de trabajo por request.

    El commit/rollback vive AQUÍ, no en los repositorios. Un request = una
    transacción: si el handler termina bien se hace un único commit; si algo
    lanza (excepción de dominio, HTTPException, error de integridad) se revierte
    todo. Los repositorios solo hacen `add`/`flush`; ninguno llama `commit()`.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
