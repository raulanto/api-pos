from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import (
    require_permission, UsuarioAutenticado, sucursal_scope, verificar_alcance_sucursal,
)
from app.shared.responses import (
    ApiResponse, EnvelopeRoute, Page, PageParams, Sort,
    page_params, make_sort_dependency, ok, page_response,
)
from app.shared.filtering import active_filters
from app.modules.clientes.domain import exceptions as cexc
from app.modules.clientes.application.dtos import FiltroClientes
from app.modules.clientes.infrastructure.api.schemas import (
    CrearClienteRequest, ActualizarClienteRequest, AbonarClienteRequest,
    CambiarLimiteCreditoRequest, ClienteResponse,
)
from app.modules.clientes.infrastructure.persistence.cliente_repository_impl import (
    SqlAlchemyClienteRepository,
)
from app.modules.clientes.application.use_cases.crear_cliente import (
    CrearClienteUseCase, CrearClienteInput,
)
from app.modules.clientes.application.use_cases.obtener_cliente import ObtenerClienteUseCase
from app.modules.clientes.application.use_cases.listar_clientes import ListarClientesUseCase
from app.modules.clientes.application.use_cases.gestionar_cliente import (
    ActualizarClienteUseCase, ActualizarClienteInput,
    DesactivarClienteUseCase,
    AbonarClienteUseCase, AbonarClienteInput,
    CambiarLimiteCreditoUseCase, CambiarLimiteCreditoInput,
)
# Lectura cruzada (solo lectura) del historial de compras del cliente.
from app.modules.ventas.application.dtos import FiltroVentas
from app.modules.ventas.application.use_cases.listar_ventas import ListarVentasUseCase
from app.modules.ventas.infrastructure.persistence.repositories_impl import SqlAlchemyVentaRepository
from app.modules.ventas.infrastructure.api.schemas import VentaListItem

router = APIRouter(route_class=EnvelopeRoute)

_NOT_FOUND = (cexc.ClienteNoEncontrado,)
_CONFLICT = (cexc.EmailClienteDuplicado, cexc.ClienteConDeuda)
_BAD_REQUEST = (
    cexc.AbonoInvalido, cexc.LimiteCreditoInvalido, cexc.LimiteCreditoExcedido, ValueError,
)

_ORDEN_CLIENTES = make_sort_dependency({"created_at", "nombre", "saldo_credito"}, "nombre:asc")
_ORDEN_VENTAS = make_sort_dependency({"created_at"}, "created_at:desc")


def _traducir(error: Exception) -> HTTPException:
    if isinstance(error, _NOT_FOUND):
        return HTTPException(status.HTTP_404_NOT_FOUND, detail=str(error))
    if isinstance(error, _CONFLICT):
        return HTTPException(status.HTTP_409_CONFLICT, detail=str(error))
    if isinstance(error, _BAD_REQUEST):
        return HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(error))
    raise error


def _repo(db: AsyncSession) -> SqlAlchemyClienteRepository:
    return SqlAlchemyClienteRepository(db)


def _exige_sucursal(actual: UsuarioAutenticado) -> UUID:
    if not actual.sucursal_id:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail="El usuario no tiene una sucursal asignada"
        )
    return actual.sucursal_id


def _sucursal_efectiva(actual: UsuarioAutenticado, pedida: UUID | None) -> UUID | None:
    alcance = sucursal_scope(actual)
    if alcance is None:
        return pedida
    if pedida is not None and pedida != alcance:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Fuera del alcance de su sucursal")
    return alcance


async def _obtener_en_alcance(db: AsyncSession, actual: UsuarioAutenticado, cliente_id: UUID):
    try:
        cliente = await ObtenerClienteUseCase(_repo(db)).ejecutar(cliente_id)
    except Exception as e:
        raise _traducir(e)
    verificar_alcance_sucursal(actual, cliente.sucursal_id)
    return cliente


# ========================================================================== #
@router.post(
    "/", response_model=ApiResponse[ClienteResponse], status_code=status.HTTP_201_CREATED,
)
async def crear_cliente(
    body: CrearClienteRequest,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("clientes.crear")),
):
    sucursal_id = _exige_sucursal(actual)
    try:
        cliente = await CrearClienteUseCase(_repo(db)).ejecutar(CrearClienteInput(
            sucursal_id=sucursal_id,
            nombre=body.nombre,
            email=body.email,
            telefono=body.telefono,
            rfc_identificacion=body.rfc_identificacion,
            limite_credito=body.limite_credito,
        ))
    except Exception as e:
        raise _traducir(e)
    return ok(cliente)


@router.get("/", response_model=ApiResponse[list[ClienteResponse]])
async def listar_clientes(
    request: Request,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("clientes.leer")),
    q: str | None = Query(default=None, description="Busca en nombre y email"),
    activo: bool | None = Query(default=None),
    con_saldo_pendiente: bool = Query(default=False),
    sucursal_id: UUID | None = Query(default=None),
    paginacion: PageParams = Depends(page_params),
    orden: Sort = Depends(_ORDEN_CLIENTES),
):
    efectiva = _sucursal_efectiva(actual, sucursal_id)
    filtro = FiltroClientes(
        sucursal_id=efectiva, activo=activo, busqueda=q,
        con_saldo_pendiente=con_saldo_pendiente,
    )
    pagina: Page = await ListarClientesUseCase(_repo(db)).ejecutar(filtro, paginacion, orden)
    return page_response(
        request, pagina, paginacion, sort=orden, filters=active_filters(filtro),
    )


@router.get("/{cliente_id}", response_model=ApiResponse[ClienteResponse])
async def obtener_cliente(
    cliente_id: UUID,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("clientes.leer")),
):
    return ok(await _obtener_en_alcance(db, actual, cliente_id))


@router.get("/{cliente_id}/ventas", response_model=ApiResponse[list[VentaListItem]])
async def historial_ventas_cliente(
    cliente_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("clientes.leer")),
    paginacion: PageParams = Depends(page_params),
    orden: Sort = Depends(_ORDEN_VENTAS),
):
    await _obtener_en_alcance(db, actual, cliente_id)  # valida existencia + alcance
    filtro = FiltroVentas(cliente_id=cliente_id)
    pagina = await ListarVentasUseCase(SqlAlchemyVentaRepository(db)).ejecutar(
        filtro, paginacion, orden,
    )
    pagina.items = [VentaListItem.model_validate(v) for v in pagina.items]
    return page_response(
        request, pagina, paginacion, sort=orden,
        filters={"cliente_id": str(cliente_id)},
    )


@router.patch("/{cliente_id}", response_model=ApiResponse[ClienteResponse])
async def actualizar_cliente(
    cliente_id: UUID,
    body: ActualizarClienteRequest,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("clientes.editar")),
):
    await _obtener_en_alcance(db, actual, cliente_id)
    try:
        cliente = await ActualizarClienteUseCase(_repo(db)).ejecutar(ActualizarClienteInput(
            cliente_id=cliente_id,
            nombre=body.nombre,
            email=body.email,
            cambiar_email=body.cambiar_email,
            telefono=body.telefono,
            rfc_identificacion=body.rfc_identificacion,
        ))
    except Exception as e:
        raise _traducir(e)
    return ok(cliente)


@router.patch("/{cliente_id}/desactivar", response_model=ApiResponse[ClienteResponse])
async def desactivar_cliente(
    cliente_id: UUID,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("clientes.eliminar")),
):
    await _obtener_en_alcance(db, actual, cliente_id)
    try:
        cliente = await DesactivarClienteUseCase(_repo(db)).ejecutar(cliente_id)
    except Exception as e:
        raise _traducir(e)
    return ok(cliente)


@router.post("/{cliente_id}/abonar", response_model=ApiResponse[ClienteResponse])
async def abonar_cliente(
    cliente_id: UUID,
    body: AbonarClienteRequest,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("clientes.editar")),
):
    await _obtener_en_alcance(db, actual, cliente_id)
    try:
        cliente = await AbonarClienteUseCase(_repo(db)).ejecutar(AbonarClienteInput(
            cliente_id=cliente_id, monto=body.monto,
        ))
    except Exception as e:
        raise _traducir(e)
    return ok(cliente)


@router.patch("/{cliente_id}/credito", response_model=ApiResponse[ClienteResponse])
async def cambiar_limite_credito(
    cliente_id: UUID,
    body: CambiarLimiteCreditoRequest,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("clientes.credito.gestionar")),
):
    await _obtener_en_alcance(db, actual, cliente_id)
    try:
        cliente = await CambiarLimiteCreditoUseCase(_repo(db)).ejecutar(CambiarLimiteCreditoInput(
            cliente_id=cliente_id, nuevo_limite=body.limite_credito,
        ))
    except Exception as e:
        raise _traducir(e)
    return ok(cliente)
