from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import (
    require_permission, UsuarioAutenticado, sucursal_scope, verificar_alcance_sucursal,
)
from app.shared.responses import (
    ApiResponse, EnvelopeRoute, PageParams, Sort,
    page_params, make_sort_dependency, make_include_dependency, ok, page_response,
)
from app.shared.filtering import active_filters
from app.modules.ventas.application.dtos import FiltroVentas
from app.modules.ventas.domain.value_objects import EstadoVenta
from app.modules.ventas.domain import exceptions as vexc
from app.modules.clientes.domain.exceptions import LimiteCreditoExcedido, ClienteNoEncontrado
from app.modules.inventario.domain.exceptions import StockInsuficiente, ProductoNoEncontrado
from app.modules.ventas.infrastructure.api.schemas import (
    CrearVentaRequest, AnularVentaRequest, VentaResponse, VentaListItem,
    AbrirCajaTurnoRequest, CerrarCajaTurnoRequest, CajaTurnoResponse, ResumenTurnoResponse,
)
from app.modules.ventas.application.use_cases.crear_venta import (
    CrearVentaUseCase, CrearVentaInput, LineaInput, PagoInput,
)
from app.modules.ventas.application.use_cases.anular_venta import (
    AnularVentaUseCase, AnularVentaInput,
)
from app.modules.ventas.application.use_cases.gestionar_caja import (
    AbrirCajaTurnoUseCase, AbrirCajaTurnoInput,
    CerrarCajaTurnoUseCase, CerrarCajaTurnoInput,
    ObtenerTurnoActualUseCase, ObtenerResumenTurnoUseCase,
)
from app.modules.ventas.application.use_cases.listar_ventas import (
    ListarVentasUseCase, ObtenerVentaUseCase,
)
from app.modules.ventas.infrastructure.persistence.repositories_impl import (
    SqlAlchemyVentaRepository, SqlAlchemyCajaTurnoRepository,
)
from app.modules.clientes.infrastructure.persistence.cliente_repository_impl import (
    SqlAlchemyClienteRepository,
)
from app.modules.ventas.infrastructure.adapters.inventario_port_impl import InventarioPortImpl
from app.modules.ventas.infrastructure.adapters.event_port_impl import EventPortImpl

router = APIRouter(route_class=EnvelopeRoute)
caja_router = APIRouter(route_class=EnvelopeRoute)

_ORDEN_VENTAS = make_sort_dependency({"created_at"}, "created_at:desc")
_INC_VENTAS = make_include_dependency({"cliente", "usuario", "caja_turno"})


# --------------------------------------------------------------------------- #
# Mapeo de excepciones de dominio -> HTTP
# --------------------------------------------------------------------------- #
_NOT_FOUND = (vexc.VentaNoEncontrada, vexc.TurnoNoEncontrado, ClienteNoEncontrado, ProductoNoEncontrado)
_CONFLICT = (vexc.VentaYaCancelada, vexc.TurnoYaAbierto, vexc.TurnoYaCerrado)
_FORBIDDEN = (vexc.AnulacionNoPermitida, vexc.CierreTurnoNoPermitido)
_BAD_REQUEST = (
    vexc.CajaNoAbierta, vexc.VentaCreditoSinCliente, vexc.VentaSinLineas,
    vexc.TurnoDeOtraSucursal, LimiteCreditoExcedido, StockInsuficiente, ValueError,
)


def _traducir(error: Exception) -> HTTPException:
    if isinstance(error, _NOT_FOUND):
        return HTTPException(status.HTTP_404_NOT_FOUND, detail=str(error))
    if isinstance(error, _CONFLICT):
        return HTTPException(status.HTTP_409_CONFLICT, detail=str(error))
    if isinstance(error, _FORBIDDEN):
        return HTTPException(status.HTTP_403_FORBIDDEN, detail=str(error))
    if isinstance(error, _BAD_REQUEST):
        return HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(error))
    raise error


def _sucursal_efectiva(actual: UsuarioAutenticado, pedida: UUID | None) -> UUID | None:
    """Roles no globales quedan atados a su sucursal (mismo criterio que inventario)."""
    alcance = sucursal_scope(actual)
    if alcance is None:
        return pedida
    if pedida is not None and pedida != alcance:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Fuera del alcance de su sucursal")
    return alcance


def _exige_sucursal(actual: UsuarioAutenticado) -> UUID:
    if not actual.sucursal_id:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail="El usuario no tiene una sucursal asignada"
        )
    return actual.sucursal_id


def _venta_use_case(db: AsyncSession) -> CrearVentaUseCase:
    return CrearVentaUseCase(
        venta_repo=SqlAlchemyVentaRepository(db),
        caja_repo=SqlAlchemyCajaTurnoRepository(db),
        inventario=InventarioPortImpl(db),
        cliente_repo=SqlAlchemyClienteRepository(db),
        event_port=EventPortImpl(db),
    )


def _anular_use_case(db: AsyncSession) -> AnularVentaUseCase:
    return AnularVentaUseCase(
        venta_repo=SqlAlchemyVentaRepository(db),
        caja_repo=SqlAlchemyCajaTurnoRepository(db),
        inventario=InventarioPortImpl(db),
        cliente_repo=SqlAlchemyClienteRepository(db),
        event_port=EventPortImpl(db),
    )


# ========================================================================== #
# VENTAS
# ========================================================================== #
@router.post(
    "/", response_model=ApiResponse[VentaResponse], status_code=status.HTTP_201_CREATED,
)
async def crear_venta(
    body: CrearVentaRequest,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("ventas.crear")),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    sucursal_id = _exige_sucursal(actual)
    entrada = CrearVentaInput(
        sucursal_id=sucursal_id,
        caja_turno_id=body.caja_turno_id,
        usuario_id=actual.id,
        cliente_id=body.cliente_id,
        descuento_total=body.descuento_total,
        lineas=[
            LineaInput(
                producto_id=l.producto_id, cantidad=l.cantidad,
                precio_unitario=l.precio_unitario, descuento_linea=l.descuento_linea,
                impuesto_tasa=l.impuesto_tasa, producto_unidad_id=l.producto_unidad_id,
            ) for l in body.lineas
        ],
        pagos=[PagoInput(monto=p.monto, metodo_pago=p.metodo_pago) for p in body.pagos],
        idempotency_key=idempotency_key,
    )
    try:
        venta = await _venta_use_case(db).ejecutar(entrada)
    except Exception as e:
        raise _traducir(e)
    return ok(venta)


@router.get("/", response_model=ApiResponse[list[VentaListItem]])
async def listar_ventas(
    request: Request,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("ventas.leer")),
    sucursal_id: UUID | None = Query(default=None),
    caja_turno_id: UUID | None = Query(default=None),
    cliente_id: UUID | None = Query(default=None),
    estado: EstadoVenta | None = Query(default=None),
    desde: datetime | None = Query(default=None),
    hasta: datetime | None = Query(default=None),
    paginacion: PageParams = Depends(page_params),
    orden: Sort = Depends(_ORDEN_VENTAS),
    include: frozenset[str] = Depends(_INC_VENTAS),
):
    efectiva = _sucursal_efectiva(actual, sucursal_id)
    filtro = FiltroVentas(
        sucursal_id=efectiva, caja_turno_id=caja_turno_id, cliente_id=cliente_id,
        estado=estado, desde=desde, hasta=hasta,
    )
    pagina = await ListarVentasUseCase(SqlAlchemyVentaRepository(db)).ejecutar(
        filtro, paginacion, orden, include,
    )
    pagina.items = [VentaListItem.model_validate(v) for v in pagina.items]
    return page_response(
        request, pagina, paginacion, sort=orden, filters=active_filters(filtro),
    )


@router.get("/{venta_id}", response_model=ApiResponse[VentaResponse])
async def obtener_venta(
    venta_id: UUID,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("ventas.leer")),
    include: frozenset[str] = Depends(_INC_VENTAS),
):
    try:
        venta = await ObtenerVentaUseCase(SqlAlchemyVentaRepository(db)).ejecutar(venta_id, include)
    except Exception as e:
        raise _traducir(e)
    verificar_alcance_sucursal(actual, venta.sucursal_id)
    return ok(venta)


@router.patch("/{venta_id}/anular", response_model=ApiResponse[VentaResponse])
async def anular_venta(
    venta_id: UUID,
    body: AnularVentaRequest,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("ventas.anular")),
):
    try:
        existente = await ObtenerVentaUseCase(SqlAlchemyVentaRepository(db)).ejecutar(venta_id)
        verificar_alcance_sucursal(actual, existente.sucursal_id)
        venta = await _anular_use_case(db).ejecutar(AnularVentaInput(
            venta_id=venta_id,
            usuario_id=actual.id,
            motivo=body.motivo,
            puede_anular_cerradas=actual.ve_todas_las_sucursales,
        ))
    except HTTPException:
        raise
    except Exception as e:
        raise _traducir(e)
    return ok(venta)


# ========================================================================== #
# CAJA
# ========================================================================== #
@caja_router.post(
    "/abrir", response_model=ApiResponse[CajaTurnoResponse], status_code=status.HTTP_201_CREATED,
)
async def abrir_turno(
    body: AbrirCajaTurnoRequest,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("ventas.crear")),
):
    sucursal_id = _exige_sucursal(actual)
    try:
        turno = await AbrirCajaTurnoUseCase(
            SqlAlchemyCajaTurnoRepository(db), EventPortImpl(db)
        ).ejecutar(AbrirCajaTurnoInput(
            sucursal_id=sucursal_id, usuario_id=actual.id, saldo_inicial=body.saldo_inicial,
        ))
    except Exception as e:
        raise _traducir(e)
    return ok(turno)


@caja_router.post("/{turno_id}/cerrar", response_model=ApiResponse[CajaTurnoResponse])
async def cerrar_turno(
    turno_id: UUID,
    body: CerrarCajaTurnoRequest,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("ventas.crear")),
):
    try:
        turno = await CerrarCajaTurnoUseCase(
            SqlAlchemyCajaTurnoRepository(db), EventPortImpl(db)
        ).ejecutar(CerrarCajaTurnoInput(
            caja_turno_id=turno_id,
            usuario_id=actual.id,
            saldo_final_declarado=body.saldo_final_declarado,
            puede_cerrar_ajeno=actual.ve_todas_las_sucursales,
        ))
    except Exception as e:
        raise _traducir(e)
    return ok(turno)


@caja_router.get("/actual", response_model=ApiResponse[CajaTurnoResponse])
async def turno_actual(
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("ventas.leer")),
):
    sucursal_id = _exige_sucursal(actual)
    try:
        turno = await ObtenerTurnoActualUseCase(SqlAlchemyCajaTurnoRepository(db)).ejecutar(
            actual.id, sucursal_id
        )
    except Exception as e:
        raise _traducir(e)
    return ok(turno)


@caja_router.get("/{turno_id}", response_model=ApiResponse[ResumenTurnoResponse])
async def resumen_turno(
    turno_id: UUID,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("ventas.leer")),
):
    try:
        resumen = await ObtenerResumenTurnoUseCase(SqlAlchemyCajaTurnoRepository(db)).ejecutar(turno_id)
    except Exception as e:
        raise _traducir(e)
    verificar_alcance_sucursal(actual, resumen.turno.sucursal_id)
    return ok(ResumenTurnoResponse(
        turno=CajaTurnoResponse.model_validate(resumen.turno),
        total_efectivo=resumen.total_efectivo,
        cantidad_ventas=resumen.cantidad_ventas,
        saldo_esperado=resumen.saldo_esperado,
    ))
