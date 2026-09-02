from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import (
    get_current_user, require_permission, UsuarioAutenticado,
    invalidar_cache_permisos, sucursal_scope, verificar_alcance_sucursal,
)
from app.core.rate_limit import login_rate_limiter
from app.shared.responses import (
    ApiResponse, EnvelopeRoute, PageParams, Sort,
    page_params, make_sort_dependency, make_include_dependency, ok, page_response,
)
from app.modules.usuarios.infrastructure.api.schemas import (
    CrearUsuarioRequest, EditarUsuarioRequest, CambiarRolRequest, CambiarPasswordRequest,
    UsuarioResponse, LoginRequest, TokenResponse, RefreshRequest, LogoutRequest,
)
from app.modules.usuarios.application.use_cases.crear_usuario import CrearUsuarioUseCase, CrearUsuarioInput
from app.modules.usuarios.application.use_cases.autenticar_usuario import AutenticarUsuarioUseCase, AutenticarUsuarioInput
from app.modules.usuarios.application.use_cases.refrescar_token import RefrescarTokenUseCase, RefrescarTokenInput
from app.modules.usuarios.application.use_cases.cerrar_sesion import CerrarSesionUseCase, CerrarSesionInput
from app.modules.usuarios.application.use_cases.listar_usuarios import ListarUsuariosUseCase, ListarUsuariosInput
from app.modules.usuarios.application.use_cases.obtener_usuario import ObtenerUsuarioUseCase
from app.modules.usuarios.application.use_cases.editar_usuario import EditarUsuarioUseCase, EditarUsuarioInput
from app.modules.usuarios.application.use_cases.cambiar_rol_usuario import CambiarRolUsuarioUseCase, CambiarRolUsuarioInput
from app.modules.usuarios.application.use_cases.desactivar_usuario import DesactivarUsuarioUseCase, DesactivarUsuarioInput
from app.modules.usuarios.application.use_cases.cambiar_password import CambiarPasswordUseCase, CambiarPasswordInput
from app.modules.usuarios.infrastructure.persistence.usuario_repository_impl import SqlAlchemyUsuarioRepository
from app.modules.usuarios.infrastructure.persistence.catalogos_repository_impl import (
    SqlAlchemyRolRepository, SqlAlchemySucursalRepository,
)
from app.modules.usuarios.infrastructure.persistence.refresh_token_repository_impl import SqlAlchemyRefreshTokenRepository
from app.modules.usuarios.domain.exceptions import (
    RolNoEncontrado, SucursalNoEncontrada, EmailDuplicado, CredencialesInvalidas,
    PasswordInvalida, UsuarioNoEncontrado, UltimoAdminActivo, AutoDesactivacionNoPermitida,
    RefreshTokenInvalido,
)

router = APIRouter(route_class=EnvelopeRoute)

_BAD_REQUEST = (
    RolNoEncontrado, SucursalNoEncontrada, EmailDuplicado, PasswordInvalida,
    UltimoAdminActivo, AutoDesactivacionNoPermitida,
)

_ORDEN_USUARIOS = make_sort_dependency(
    {"nombre", "email", "created_at", "last_login_at"}, "nombre:asc"
)
_INC_USUARIOS = make_include_dependency({"rol", "sucursal"})


def _cliente_info(request: Request) -> tuple[str | None, str | None]:
    ua = request.headers.get("user-agent")
    ip = request.client.host if request.client else None
    return ua, ip


# --------------------------------------------------------------------------- #
# Dependencias de casos de uso
# --------------------------------------------------------------------------- #
def get_crear_usuario_use_case(db: AsyncSession = Depends(get_db)) -> CrearUsuarioUseCase:
    return CrearUsuarioUseCase(
        usuario_repo=SqlAlchemyUsuarioRepository(db),
        rol_repo=SqlAlchemyRolRepository(db),
        sucursal_repo=SqlAlchemySucursalRepository(db),
    )


def get_autenticar_usuario_use_case(db: AsyncSession = Depends(get_db)) -> AutenticarUsuarioUseCase:
    return AutenticarUsuarioUseCase(
        usuario_repo=SqlAlchemyUsuarioRepository(db),
        rol_repo=SqlAlchemyRolRepository(db),
        refresh_token_repo=SqlAlchemyRefreshTokenRepository(db),
    )


def get_refrescar_token_use_case(db: AsyncSession = Depends(get_db)) -> RefrescarTokenUseCase:
    return RefrescarTokenUseCase(
        refresh_token_repo=SqlAlchemyRefreshTokenRepository(db),
        usuario_repo=SqlAlchemyUsuarioRepository(db),
        rol_repo=SqlAlchemyRolRepository(db),
    )


def get_cerrar_sesion_use_case(db: AsyncSession = Depends(get_db)) -> CerrarSesionUseCase:
    return CerrarSesionUseCase(refresh_token_repo=SqlAlchemyRefreshTokenRepository(db))


# --------------------------------------------------------------------------- #
# Autenticación
# --------------------------------------------------------------------------- #
# Los endpoints de token NO usan el sobre ApiResponse: siguen el contrato
# estándar OAuth2 ({access_token, token_type, ...}) porque Swagger UI, los
# clientes OAuth y el front esperan esas claves en la raíz. Envolverlos rompe
# el "Authorize" y hace que todo request autenticado devuelva 401.
@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    request: Request,
    use_case: AutenticarUsuarioUseCase = Depends(get_autenticar_usuario_use_case),
):
    ua, ip = _cliente_info(request)
    login_rate_limiter.check(clave=f"{ip}:{body.email}")
    try:
        return await use_case.ejecutar(AutenticarUsuarioInput(
            email=body.email, password_plano=body.password, user_agent=ua, ip=ip,
        ))
    except CredencialesInvalidas as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))


@router.post(
    "/token",
    response_model=TokenResponse,
    summary="Login OAuth2 (formulario) — lo usa el botón Authorize de Swagger",
)
async def login_oauth2(
    request: Request,
    form: OAuth2PasswordRequestForm = Depends(),
    use_case: AutenticarUsuarioUseCase = Depends(get_autenticar_usuario_use_case),
):
    """Equivalente a `POST /login` pero con cuerpo
    `application/x-www-form-urlencoded` (`username` = email, `password`).

    Existe para que el flujo *password* de Swagger UI funcione; el front-end
    sigue usando `POST /login` (JSON).
    """
    ua, ip = _cliente_info(request)
    login_rate_limiter.check(clave=f"{ip}:{form.username}")
    try:
        return await use_case.ejecutar(AutenticarUsuarioInput(
            email=form.username, password_plano=form.password, user_agent=ua, ip=ip,
        ))
    except CredencialesInvalidas as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))


@router.post("/refresh", response_model=TokenResponse)
async def refrescar(
    body: RefreshRequest,
    request: Request,
    use_case: RefrescarTokenUseCase = Depends(get_refrescar_token_use_case),
):
    ua, ip = _cliente_info(request)
    try:
        return await use_case.ejecutar(RefrescarTokenInput(
            refresh_token=body.refresh_token, user_agent=ua, ip=ip,
        ))
    except RefreshTokenInvalido as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    body: LogoutRequest,
    use_case: CerrarSesionUseCase = Depends(get_cerrar_sesion_use_case),
    actual: UsuarioAutenticado = Depends(get_current_user),
):
    await use_case.ejecutar(CerrarSesionInput(refresh_token=body.refresh_token))


# --------------------------------------------------------------------------- #
# CRUD de usuarios
# --------------------------------------------------------------------------- #
@router.get("/me", response_model=ApiResponse[UsuarioResponse])
async def usuario_actual(
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(get_current_user),
    include: frozenset[str] = Depends(_INC_USUARIOS),
):
    if not include:
        return ok(actual.usuario)
    usuario = await ObtenerUsuarioUseCase(SqlAlchemyUsuarioRepository(db)).ejecutar(
        actual.id, include,
    )
    return ok(usuario)


@router.get("", response_model=ApiResponse[list[UsuarioResponse]])
async def listar_usuarios(
    request: Request,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("usuarios.leer")),
    paginacion: PageParams = Depends(page_params),
    orden: Sort = Depends(_ORDEN_USUARIOS),
    include: frozenset[str] = Depends(_INC_USUARIOS),
):
    entrada = ListarUsuariosInput(sucursal_id=sucursal_scope(actual))
    pagina = await ListarUsuariosUseCase(SqlAlchemyUsuarioRepository(db)).ejecutar(
        entrada, paginacion, orden, include,
    )
    return page_response(request, pagina, paginacion, sort=orden)


@router.get("/{usuario_id}", response_model=ApiResponse[UsuarioResponse])
async def obtener_usuario(
    usuario_id: UUID,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("usuarios.leer")),
    include: frozenset[str] = Depends(_INC_USUARIOS),
):
    use_case = ObtenerUsuarioUseCase(SqlAlchemyUsuarioRepository(db))
    try:
        usuario = await use_case.ejecutar(usuario_id, include)
    except UsuarioNoEncontrado as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    verificar_alcance_sucursal(actual, usuario.sucursal_id)
    return ok(usuario)


@router.post(
    "", response_model=ApiResponse[UsuarioResponse], status_code=status.HTTP_201_CREATED,
)
async def crear_usuario(
    body: CrearUsuarioRequest,
    use_case: CrearUsuarioUseCase = Depends(get_crear_usuario_use_case),
    actual: UsuarioAutenticado = Depends(require_permission("usuarios.crear")),
):
    try:
        usuario = await use_case.ejecutar(CrearUsuarioInput(
            sucursal_id=body.sucursal_id,
            rol_id=body.rol_id,
            nombre=body.nombre,
            email=body.email,
            password_plano=body.password,
        ))
    except _BAD_REQUEST as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return ok(usuario)


@router.patch("/{usuario_id}", response_model=ApiResponse[UsuarioResponse])
async def editar_usuario(
    usuario_id: UUID,
    body: EditarUsuarioRequest,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("usuarios.editar")),
):
    use_case = EditarUsuarioUseCase(
        usuario_repo=SqlAlchemyUsuarioRepository(db),
        sucursal_repo=SqlAlchemySucursalRepository(db),
    )
    data = EditarUsuarioInput(
        usuario_id=usuario_id,
        nombre=body.nombre,
        email=body.email,
        sucursal_id=body.sucursal_id,
        _sucursal_presente="sucursal_id" in body.model_fields_set,
    )
    try:
        usuario = await use_case.ejecutar(data)
    except UsuarioNoEncontrado as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except _BAD_REQUEST as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return ok(usuario)


@router.patch("/{usuario_id}/rol", response_model=ApiResponse[UsuarioResponse])
async def cambiar_rol(
    usuario_id: UUID,
    body: CambiarRolRequest,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("roles.gestionar")),
):
    use_case = CambiarRolUsuarioUseCase(
        usuario_repo=SqlAlchemyUsuarioRepository(db),
        rol_repo=SqlAlchemyRolRepository(db),
    )
    try:
        usuario = await use_case.ejecutar(
            CambiarRolUsuarioInput(usuario_id=usuario_id, nuevo_rol_id=body.rol_id)
        )
    except UsuarioNoEncontrado as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except _BAD_REQUEST as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    invalidar_cache_permisos(usuario.rol_id)
    return ok(usuario)


@router.patch("/{usuario_id}/desactivar", response_model=ApiResponse[UsuarioResponse])
async def desactivar_usuario(
    usuario_id: UUID,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("usuarios.desactivar")),
):
    use_case = DesactivarUsuarioUseCase(
        usuario_repo=SqlAlchemyUsuarioRepository(db),
        rol_repo=SqlAlchemyRolRepository(db),
    )
    try:
        usuario = await use_case.ejecutar(DesactivarUsuarioInput(
            usuario_id=usuario_id, solicitante_id=actual.id,
        ))
    except UsuarioNoEncontrado as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except _BAD_REQUEST as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return ok(usuario)


@router.post("/{usuario_id}/cambiar-password", status_code=status.HTTP_204_NO_CONTENT)
async def cambiar_password(
    usuario_id: UUID,
    body: CambiarPasswordRequest,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(get_current_user),
):
    es_propia = usuario_id == actual.id
    if not es_propia and not actual.tiene_permiso("usuarios.editar"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No puede cambiar la contraseña de otro usuario",
        )

    use_case = CambiarPasswordUseCase(
        usuario_repo=SqlAlchemyUsuarioRepository(db),
        refresh_token_repo=SqlAlchemyRefreshTokenRepository(db),
    )
    try:
        await use_case.ejecutar(CambiarPasswordInput(
            usuario_id=usuario_id,
            solicitante_id=actual.id,
            password_actual=body.password_actual,
            password_nueva=body.password_nueva,
            solicitante_es_gestor=(not es_propia and actual.tiene_permiso("usuarios.editar")),
        ))
    except UsuarioNoEncontrado as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except CredencialesInvalidas as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    except PasswordInvalida as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
