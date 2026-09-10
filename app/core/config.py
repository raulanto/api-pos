from decimal import Decimal

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

    # Zona horaria local del negocio: interpreta `hora_desde`/`hora_hasta` y
    # `dias_semana` de las promociones (los `momento` en BD son UTC).
    app_timezone: str = "America/Mexico_City"

    # Caja: si |diferencia| del cierre >= este monto, el turno queda
    # `cerrado_con_diferencia` y exige `nota_cierre` + conciliación de un gerente.
    # ponytail: umbral global, no por sucursal/caja.
    caja_diferencia_umbral: Decimal = Decimal("20.00")

    # --- Pedidos / órdenes ---
    # Producto de tipo SERVICIO que representa el cargo de envío a domicilio. Al
    # facturar un pedido con `costo_envio > 0` se agrega como una línea con ese
    # producto (así el envío entra en ticket, reportes y arqueo sin tocar el
    # esquema de `venta`). Si es None y hay `costo_envio`, la facturación falla.
    pedidos_producto_envio_id: str | None = None

    # --- Seed del administrador inicial (usado por la migración-seeder) ---
    seed_admin_email: str | None = None
    seed_admin_password: str | None = None
    seed_admin_nombre: str = "Administrador"

    # --- Rate limiting del login ---
    login_rate_limit_max: int = 5          # intentos permitidos por ventana
    login_rate_limit_window_seconds: int = 60

    # --- Almacenamiento de imágenes en S3 (LocalStack en dev) ---
    # `s3_endpoint_url`: endpoint que usa la API para subir/borrar (dentro de
    #   compose es http://localstack:4566; fuera de Docker, http://localhost:4566).
    # `s3_public_endpoint_url`: endpoint que se firma en las URLs GET que abre el
    #   navegador (siempre el host alcanzable desde afuera, http://localhost:4566).
    # Ambos None => se usa AWS real (endpoint por defecto de boto3).
    s3_endpoint_url: str | None = None
    s3_public_endpoint_url: str | None = None
    s3_bucket_imagenes: str = "pos-imagenes"
    s3_region: str = "us-east-1"
    aws_access_key_id: str = "test"
    aws_secret_access_key: str = "test"
    s3_presign_expira_segundos: int = 3600
    imagen_max_bytes: int = 5 * 1024 * 1024   # 5 MiB por archivo

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
