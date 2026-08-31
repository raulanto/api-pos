from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    entorno: str = "development"       # development | staging | production
    database_url: str = "postgresql+asyncpg://postgres:password@localhost:5432/pos_db"
    jwt_secret: str = "supersecret"
    jwt_expire_minutes: int = 30
    cors_origins: str = "http://localhost:3000,http://localhost:5173"

    model_config = SettingsConfigDict(env_file=".env")

settings = Settings()
