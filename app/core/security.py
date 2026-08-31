import hashlib
import secrets
import bcrypt
from datetime import datetime, timedelta, timezone
import jwt
from app.core.config import settings

ALGORITHM = "HS256"

# bcrypt solo considera los primeros 72 bytes de la contraseña; las versiones
# recientes de la librería lanzan error en vez de truncar, así que truncamos acá.
_BCRYPT_MAX_BYTES = 72


def _to_bcrypt_bytes(password: str) -> bytes:
    return password.encode("utf-8")[:_BCRYPT_MAX_BYTES]


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(_to_bcrypt_bytes(plain_password), hashed_password.encode("utf-8"))
    except ValueError:
        return False


def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(_to_bcrypt_bytes(password), bcrypt.gensalt()).decode("utf-8")


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret, algorithm=ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> dict | None:
    try:
        decoded_token = jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
        return decoded_token
    except jwt.PyJWTError:
        return None


# --- Refresh tokens ---
# El refresh token es un valor opaco de alta entropía. Se entrega al cliente en
# claro una sola vez y en BD solo se guarda su hash (SHA-256), igual que se hace
# con las contraseñas. No hace falta bcrypt: al ser aleatorio de 256 bits no es
# atacable por fuerza bruta / diccionario.

def generate_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def refresh_token_expiry() -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=settings.jwt_refresh_expire_days)
