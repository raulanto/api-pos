from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator

DEFAULT_JWT_SECRET = "supersecret"


class Settings(BaseSettings):
    entorno: str = "development"       # development | staging | production
    database_url: str = "postgresql+asyncpg://postgres:password@localhost:5432/pos_db"

    # --- JWT ---
    jwt_secret: str = DEFAULT_JWT_SECRET
    jwt_expire_minutes: int = 30
    jwt_refresh_expire_days: int = 14

    cors_origins: str = "http://localhost:3000,http://localhost:5173"

    # --- Seed del administrador inicial (usado por la migración-seeder) ---
    seed_admin_email: str | None = None
    seed_admin_password: str | None = None
    seed_admin_nombre: str = "Administrador"

    # --- Rate limiting del login ---
    login_rate_limit_max: int = 5          # intentos permitidos por ventana
    login_rate_limit_window_seconds: int = 60

    model_config = SettingsConfigDict(env_file=".env")

    @model_validator(mode="after")
    def _validar_jwt_secret_por_entorno(self) -> "Settings":
        if self.entorno != "development" and self.jwt_secret == DEFAULT_JWT_SECRET:
            raise ValueError(
                f"jwt_secret no puede usar el valor por defecto en entorno '{self.entorno}'. "
                "Definí la variable de entorno JWT_SECRET con un valor propio."
            )
        return self


settings = Settings()
