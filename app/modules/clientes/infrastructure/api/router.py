from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.dependencies import require_permission, UsuarioAutenticado, verificar_alcance_sucursal
from app.modules.clientes.infrastructure.api.schemas import CrearClienteRequest, ClienteResponse
from app.modules.clientes.application.use_cases.crear_cliente import CrearClienteUseCase, CrearClienteInput
from app.modules.clientes.application.use_cases.obtener_cliente import ObtenerClienteUseCase
from app.modules.clientes.infrastructure.persistence.cliente_repository_impl import SqlAlchemyClienteRepository
from app.modules.clientes.domain.exceptions import ClienteNoEncontrado
from uuid import UUID

router = APIRouter()

def get_crear_cliente_use_case(db: AsyncSession = Depends(get_db)) -> CrearClienteUseCase:
    return CrearClienteUseCase(SqlAlchemyClienteRepository(db))

def get_obtener_cliente_use_case(db: AsyncSession = Depends(get_db)) -> ObtenerClienteUseCase:
    return ObtenerClienteUseCase(SqlAlchemyClienteRepository(db))

@router.post("/", response_model=ClienteResponse, status_code=status.HTTP_201_CREATED)
async def crear_cliente(
    body: CrearClienteRequest,
    use_case: CrearClienteUseCase = Depends(get_crear_cliente_use_case),
    usuario_actual: UsuarioAutenticado = Depends(require_permission("clientes.crear")),
):
    if not usuario_actual.sucursal_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El usuario no tiene una sucursal asignada")

    cliente = await use_case.ejecutar(CrearClienteInput(
        sucursal_id=usuario_actual.sucursal_id,
        nombre=body.nombre,
        email=body.email,
        telefono=body.telefono,
        rfc_identificacion=body.rfc_identificacion,
        limite_credito=body.limite_credito
    ))
    return cliente

@router.get("/{cliente_id}", response_model=ClienteResponse)
async def obtener_cliente(
    cliente_id: UUID,
    use_case: ObtenerClienteUseCase = Depends(get_obtener_cliente_use_case),
    usuario_actual: UsuarioAutenticado = Depends(require_permission("clientes.leer")),
):
    try:
        cliente = await use_case.ejecutar(cliente_id)
    except ClienteNoEncontrado as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    verificar_alcance_sucursal(usuario_actual, cliente.sucursal_id)
    return cliente
