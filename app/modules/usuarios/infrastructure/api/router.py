from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.modules.usuarios.infrastructure.api.schemas import CrearUsuarioRequest, UsuarioResponse, LoginRequest
from app.modules.usuarios.application.use_cases.crear_usuario import CrearUsuarioUseCase, CrearUsuarioInput
from app.modules.usuarios.application.use_cases.autenticar_usuario import AutenticarUsuarioUseCase, AutenticarUsuarioInput, TokenOutput
from app.modules.usuarios.infrastructure.persistence.usuario_repository_impl import SqlAlchemyUsuarioRepository
from app.modules.usuarios.infrastructure.persistence.catalogos_repository_impl import SqlAlchemyRolRepository, SqlAlchemySucursalRepository
from app.modules.usuarios.domain.exceptions import RolNoEncontrado, SucursalNoEncontrada, EmailDuplicado, CredencialesInvalidas

router = APIRouter()

def get_crear_usuario_use_case(db: AsyncSession = Depends(get_db)) -> CrearUsuarioUseCase:
    return CrearUsuarioUseCase(
        usuario_repo=SqlAlchemyUsuarioRepository(db),
        rol_repo=SqlAlchemyRolRepository(db),
        sucursal_repo=SqlAlchemySucursalRepository(db),
    )

def get_autenticar_usuario_use_case(db: AsyncSession = Depends(get_db)) -> AutenticarUsuarioUseCase:
    return AutenticarUsuarioUseCase(
        usuario_repo=SqlAlchemyUsuarioRepository(db),
    )

@router.post("/", response_model=UsuarioResponse, status_code=status.HTTP_201_CREATED)
async def crear_usuario(
    body: CrearUsuarioRequest,
    use_case: CrearUsuarioUseCase = Depends(get_crear_usuario_use_case)
):
    try:
        usuario = await use_case.ejecutar(CrearUsuarioInput(
            sucursal_id=body.sucursal_id,
            rol_id=body.rol_id,
            nombre=body.nombre,
            email=body.email,
            password_plano=body.password,
        ))
        return usuario
    except (RolNoEncontrado, SucursalNoEncontrada, EmailDuplicado) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/login", response_model=TokenOutput)
async def login(
    body: LoginRequest,
    use_case: AutenticarUsuarioUseCase = Depends(get_autenticar_usuario_use_case)
):
    try:
        token_data = await use_case.ejecutar(AutenticarUsuarioInput(
            email=body.email,
            password_plano=body.password,
        ))
        return token_data
    except CredencialesInvalidas as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
