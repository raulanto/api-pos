from app.modules.usuarios.domain.entities import Usuario, Rol, Permiso, Sucursal
from app.modules.usuarios.infrastructure.persistence.orm_models import UsuarioORM, RolORM, PermisoORM, SucursalORM
from datetime import datetime, timezone

def to_domain_permiso(orm: PermisoORM) -> Permiso:
    return Permiso(id=orm.id, codigo=orm.codigo, descripcion=orm.descripcion)

def to_domain_rol(orm: RolORM) -> Rol:
    return Rol(
        id=orm.id,
        nombre=orm.nombre,
        descripcion=orm.descripcion,
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

def to_domain_usuario(orm: UsuarioORM) -> Usuario:
    return Usuario(
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
