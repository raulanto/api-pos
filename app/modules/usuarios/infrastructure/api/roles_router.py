from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import (
    get_current_user, require_permission, UsuarioAutenticado, invalidar_cache_permisos,
)
from app.shared.responses import ApiResponse, EnvelopeRoute, ok
from app.modules.usuarios.infrastructure.api.schemas import (
    RolResponse, PermisoResponse, CrearRolRequest, EditarRolRequest, AsignarPermisosRequest,
)
from app.modules.usuarios.infrastructure.persistence.catalogos_repository_impl import (
    SqlAlchemyRolRepository, SqlAlchemyPermisoRepository,
)
from app.modules.usuarios.application.use_cases.gestionar_roles import (
    ListarRolesUseCase, ListarPermisosUseCase,
    CrearRolUseCase, CrearRolInput,
    EditarRolUseCase, EditarRolInput,
    EliminarRolUseCase,
    AsignarPermisosRolUseCase, AsignarPermisosInput,
    QuitarPermisoRolUseCase,
)
from app.modules.usuarios.domain.exceptions import (
    RolNoEncontrado, RolAdminProtegido, CodigoRolDuplicado, PermisoNoEncontrado,
    UsuarioNoEncontrado,
)

router = APIRouter(route_class=EnvelopeRoute)

_CONFLICT = (RolAdminProtegido, CodigoRolDuplicado, UsuarioNoEncontrado)


def _rol_repo(db: AsyncSession) -> SqlAlchemyRolRepository:
    return SqlAlchemyRolRepository(db)


def _permiso_repo(db: AsyncSession) -> SqlAlchemyPermisoRepository:
    return SqlAlchemyPermisoRepository(db)


@router.get("", response_model=ApiResponse[list[RolResponse]])
async def listar_roles(
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("roles.gestionar")),
):
    return ok(await ListarRolesUseCase(_rol_repo(db)).ejecutar())


@router.post(
    "", response_model=ApiResponse[RolResponse], status_code=status.HTTP_201_CREATED,
)
async def crear_rol(
    body: CrearRolRequest,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("roles.gestionar")),
):
    use_case = CrearRolUseCase(_rol_repo(db), _permiso_repo(db))
    try:
        rol = await use_case.ejecutar(CrearRolInput(
            codigo=body.codigo, nombre=body.nombre,
            descripcion=body.descripcion, permiso_ids=body.permiso_ids,
        ))
    except PermisoNoEncontrado as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except _CONFLICT as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    return ok(rol)


@router.patch("/{rol_id}", response_model=ApiResponse[RolResponse])
async def editar_rol(
    rol_id: UUID,
    body: EditarRolRequest,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("roles.gestionar")),
):
    try:
        rol = await EditarRolUseCase(_rol_repo(db)).ejecutar(
            EditarRolInput(rol_id=rol_id, nombre=body.nombre, descripcion=body.descripcion)
        )
    except RolNoEncontrado as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return ok(rol)


@router.delete("/{rol_id}", status_code=status.HTTP_204_NO_CONTENT)
async def eliminar_rol(
    rol_id: UUID,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("roles.gestionar")),
):
    try:
        await EliminarRolUseCase(_rol_repo(db)).ejecutar(rol_id)
    except RolNoEncontrado as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except _CONFLICT as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    invalidar_cache_permisos(rol_id)


@router.post("/{rol_id}/permisos", response_model=ApiResponse[RolResponse])
async def asignar_permisos(
    rol_id: UUID,
    body: AsignarPermisosRequest,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("roles.gestionar")),
):
    use_case = AsignarPermisosRolUseCase(_rol_repo(db), _permiso_repo(db))
    try:
        rol = await use_case.ejecutar(AsignarPermisosInput(rol_id=rol_id, permiso_ids=body.permiso_ids))
    except RolNoEncontrado as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermisoNoEncontrado as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    invalidar_cache_permisos(rol_id)
    return ok(rol)


@router.delete("/{rol_id}/permisos/{permiso_id}", response_model=ApiResponse[RolResponse])
async def quitar_permiso(
    rol_id: UUID,
    permiso_id: UUID,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("roles.gestionar")),
):
    try:
        rol = await QuitarPermisoRolUseCase(_rol_repo(db)).ejecutar(rol_id, permiso_id)
    except RolNoEncontrado as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    invalidar_cache_permisos(rol_id)
    return ok(rol)


# Catálogo de permisos: solo lectura, cualquier sesión válida.
permisos_router = APIRouter(route_class=EnvelopeRoute)


@permisos_router.get("", response_model=ApiResponse[list[PermisoResponse]])
async def listar_permisos(
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(get_current_user),
):
    return ok(await ListarPermisosUseCase(_permiso_repo(db)).ejecutar())
