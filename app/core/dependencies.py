import time
import uuid
from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_access_token
from app.modules.usuarios.domain.entities import Usuario, ROL_ADMIN
from app.modules.usuarios.infrastructure.persistence.orm_models import (
    RolORM, PermisoORM, rol_permiso_table,
)
from app.modules.usuarios.infrastructure.persistence.usuario_repository_impl import (
    SqlAlchemyUsuarioRepository,
)

# `tokenUrl` apunta al endpoint OAuth2 por formulario (no al `/login` JSON), que
# es lo que consume el botón "Authorize" de Swagger UI (flujo password).
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/usuarios/token")

# Roles que ven datos de todas las sucursales (sección 11 del plan).
ROLES_GLOBALES = {ROL_ADMIN, "gerente"}


# --------------------------------------------------------------------------- #
# Caché en memoria de (codigo_rol, permisos) por rol_id.
# TTL corto: refleja cambios de permisos casi al instante sin golpear la BD
# en cada request.
# --------------------------------------------------------------------------- #
_CACHE_TTL_SECONDS = 30
_rol_cache: dict[uuid.UUID, tuple[float, str | None, frozenset[str]]] = {}


def invalidar_cache_permisos(rol_id: uuid.UUID | None = None) -> None:
    """Llamar tras editar un rol o sus permisos."""
    if rol_id is None:
        _rol_cache.clear()
    else:
        _rol_cache.pop(rol_id, None)


async def _cargar_rol(rol_id: uuid.UUID, db: AsyncSession) -> tuple[str | None, frozenset[str]]:
    ahora = time.monotonic()
    cacheado = _rol_cache.get(rol_id)
    if cacheado and cacheado[0] > ahora:
        return cacheado[1], cacheado[2]

    codigo_rol = await db.scalar(select(RolORM.codigo).where(RolORM.id == rol_id))
    filas = await db.execute(
        select(PermisoORM.codigo)
        .join(rol_permiso_table, rol_permiso_table.c.permiso_id == PermisoORM.id)
        .where(rol_permiso_table.c.rol_id == rol_id)
    )
    permisos = frozenset(filas.scalars().all())
    _rol_cache[rol_id] = (ahora + _CACHE_TTL_SECONDS, codigo_rol, permisos)
    return codigo_rol, permisos


# --------------------------------------------------------------------------- #
# Usuario autenticado
# --------------------------------------------------------------------------- #
@dataclass
class UsuarioAutenticado:
    """Wrapper del usuario del dominio + datos resueltos de su rol."""
    usuario: Usuario
    rol_codigo: str | None
    permisos: frozenset[str]

    # Passthrough de los campos más usados
    @property
    def id(self) -> uuid.UUID:
        return self.usuario.id

    @property
    def sucursal_id(self):
        return self.usuario.sucursal_id

    @property
    def rol_id(self) -> uuid.UUID:
        return self.usuario.rol_id

    @property
    def es_admin(self) -> bool:
        return self.rol_codigo == ROL_ADMIN

    @property
    def ve_todas_las_sucursales(self) -> bool:
        return self.rol_codigo in ROLES_GLOBALES

    def tiene_permiso(self, *codigos: str) -> bool:
        return any(c in self.permisos for c in codigos)


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> UsuarioAutenticado:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudieron validar las credenciales",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception

    user_id_str = payload.get("sub")
    if user_id_str is None:
        raise credentials_exception

    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        raise credentials_exception

    repo = SqlAlchemyUsuarioRepository(db)
    user = await repo.obtener_por_id(user_id)
    if user is None:
        raise credentials_exception
    if not user.activo:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario inactivo")

    rol_codigo, permisos = await _cargar_rol(user.rol_id, db)
    return UsuarioAutenticado(usuario=user, rol_codigo=rol_codigo, permisos=permisos)


# --------------------------------------------------------------------------- #
# Autorización por permiso
# --------------------------------------------------------------------------- #
def require_permission(*codigos: str):
    """
    Devuelve una dependencia de FastAPI que exige que el usuario autenticado
    tenga AL MENOS UNO de los permisos indicados (lógica OR).

        @router.post("/", dependencies=[Depends(require_permission("ventas.crear"))])

    o, si se necesita el usuario dentro del handler:

        usuario = Depends(require_permission("ventas.crear"))
    """
    if not codigos:
        raise ValueError("require_permission necesita al menos un código de permiso")

    async def dependency(
        actual: UsuarioAutenticado = Depends(get_current_user),
    ) -> UsuarioAutenticado:
        if not actual.tiene_permiso(*codigos):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requiere alguno de estos permisos: {', '.join(codigos)}",
            )
        return actual

    return dependency


def sucursal_scope(actual: UsuarioAutenticado) -> uuid.UUID | None:
    """
    Sección 11: alcance de sucursal para filtrar en repositorios.
    Devuelve None => ve todas las sucursales; si no, su propia sucursal_id.
    """
    if actual.ve_todas_las_sucursales:
        return None
    return actual.sucursal_id


def verificar_alcance_sucursal(actual: UsuarioAutenticado, sucursal_id: uuid.UUID | None) -> None:
    """Lanza 403 si `sucursal_id` cae fuera del alcance del usuario."""
    if actual.ve_todas_las_sucursales:
        return
    if sucursal_id is not None and sucursal_id != actual.sucursal_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Fuera del alcance de su sucursal",
        )
