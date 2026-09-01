from app.modules.usuarios.domain.entities import Usuario, Rol, Permiso, Sucursal, RefreshToken
from app.modules.usuarios.infrastructure.persistence.orm_models import (
    UsuarioORM, RolORM, PermisoORM, SucursalORM, RefreshTokenORM,
)


def to_domain_permiso(orm: PermisoORM) -> Permiso:
    return Permiso(id=orm.id, codigo=orm.codigo, descripcion=orm.descripcion)

def to_domain_rol(orm: RolORM) -> Rol:
    return Rol(
        id=orm.id,
        nombre=orm.nombre,
        descripcion=orm.descripcion,
        codigo=orm.codigo,
        permisos=[to_domain_permiso(p) for p in orm.permisos] if orm.permisos else []
    )

def to_domain_sucursal(orm: SucursalORM) -> Sucursal:
    return Sucursal(
        id=orm.id,
        nombre=orm.nombre,
        direccion=orm.direccion,
        telefono=orm.telefono,
        activo=orm.activo,
        created_at=orm.created_at
    )

def to_domain_usuario(orm: UsuarioORM, includes: frozenset[str] = frozenset()) -> Usuario:
    usuario = Usuario(
        id=orm.id,
        sucursal_id=orm.sucursal_id,
        rol_id=orm.rol_id,
        nombre=orm.nombre,
        email=orm.email,
        password_hash=orm.password_hash,
        activo=orm.activo,
        last_login_at=orm.last_login_at,
        created_at=orm.created_at
    )
    if "rol" in includes:
        usuario.rol = to_domain_rol(orm.rol) if orm.rol is not None else None
    if "sucursal" in includes:
        usuario.sucursal = orm.sucursal
    return usuario

def to_orm_usuario(entidad: Usuario) -> UsuarioORM:
    return UsuarioORM(
        id=entidad.id,
        sucursal_id=entidad.sucursal_id,
        rol_id=entidad.rol_id,
        nombre=entidad.nombre,
        email=entidad.email,
        password_hash=entidad.password_hash,
        activo=entidad.activo,
        last_login_at=entidad.last_login_at
    )

def to_domain_refresh_token(orm: RefreshTokenORM) -> RefreshToken:
    return RefreshToken(
        id=orm.id,
        usuario_id=orm.usuario_id,
        token_hash=orm.token_hash,
        expira_en=orm.expira_en,
        revocado=orm.revocado,
        user_agent=orm.user_agent,
        ip=orm.ip,
        created_at=orm.created_at,
    )

def to_orm_refresh_token(entidad: RefreshToken) -> RefreshTokenORM:
    return RefreshTokenORM(
        id=entidad.id,
        usuario_id=entidad.usuario_id,
        token_hash=entidad.token_hash,
        expira_en=entidad.expira_en,
        revocado=entidad.revocado,
        user_agent=entidad.user_agent,
        ip=entidad.ip,
        created_at=entidad.created_at,
    )
