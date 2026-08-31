class UsuarioNoEncontrado(Exception):
    pass

class RolNoEncontrado(Exception):
    pass

class SucursalNoEncontrada(Exception):
    pass

class EmailDuplicado(Exception):
    pass

class CredencialesInvalidas(Exception):
    pass

class PasswordInvalida(Exception):
    """La contraseña no cumple la política mínima."""
    pass

# --- Reglas de negocio de roles y permisos ---

class RolAdminProtegido(Exception):
    """No se puede eliminar ni cambiar el código del rol admin."""
    pass

class CodigoRolInmutable(Exception):
    """El código de un rol no se puede modificar una vez creado."""
    pass

class CodigoRolDuplicado(Exception):
    pass

class UltimoAdminActivo(Exception):
    """No se puede dejar el sistema sin ningún usuario admin activo."""
    pass

class PermisoNoEncontrado(Exception):
    pass

class AutoDesactivacionNoPermitida(Exception):
    """Un usuario no puede desactivarse a sí mismo."""
    pass

# --- Refresh tokens ---

class RefreshTokenInvalido(Exception):
    """El refresh token no existe, expiró o fue revocado."""
    pass
