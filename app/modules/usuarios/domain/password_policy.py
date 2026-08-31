from app.modules.usuarios.domain.exceptions import PasswordInvalida

LONGITUD_MINIMA = 8


def validar_password(password: str, email: str | None = None) -> None:
    """Política mínima (sección 12): largo >= 8 y distinta del email."""
    if len(password) < LONGITUD_MINIMA:
        raise PasswordInvalida(f"La contraseña debe tener al menos {LONGITUD_MINIMA} caracteres")
    if email and password.strip().lower() == email.strip().lower():
        raise PasswordInvalida("La contraseña no puede ser igual al email")
