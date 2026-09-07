from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, status
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
from app.modules.inventario.domain.exceptions import (
    StockInsuficiente, ProductoNoEncontrado, CantidadNoVendible,
    LoteRequerido, LoteInvalido,
)
from app.modules.ventas.infrastructure.api.schemas import (
    CrearVentaRequest, AnularVentaRequest, VentaResponse, VentaListItem,
    CotizarVentaRequest, CotizacionResponse,
    DevolverVentaRequest, DevolucionResponse,
    AbrirCajaTurnoRequest, CerrarCajaTurnoRequest, CajaTurnoResponse, ResumenTurnoResponse,
)
from app.modules.ventas.application.use_cases.crear_venta import (
    CrearVentaUseCase, CrearVentaInput, CotizarVentaInput, LineaInput, PagoInput,
)
from app.modules.ventas.application.use_cases.anular_venta import (
    AnularVentaUseCase, AnularVentaInput,
)
from app.modules.ventas.application.use_cases.devolver_venta import (
    DevolverVentaUseCase, DevolverVentaInput, DevolverVentaLineaInput,
)
from app.modules.ventas.application.use_cases.gestionar_caja import (
    AbrirCajaTurnoUseCase, AbrirCajaTurnoInput,
    CerrarCajaTurnoUseCase, CerrarCajaTurnoInput,
    ObtenerTurnoActualUseCase, ObtenerResumenTurnoUseCase,
)
from app.modules.ventas.application.use_cases.listar_ventas import (
    ListarVentasUseCase, ObtenerVentaUseCase,
)
from app.modules.ventas.application.use_cases.generar_ticket import GenerarTicketUseCase
from app.modules.ventas.infrastructure.pdf.ticket_pdf import render_ticket_pdf
from app.modules.ventas.infrastructure.persistence.repositories_impl import (
    SqlAlchemyVentaRepository, SqlAlchemyCajaTurnoRepository, SqlAlchemyDevolucionRepository,
)
from app.modules.clientes.infrastructure.persistence.cliente_repository_impl import (
    SqlAlchemyClienteRepository,
)
from app.modules.inventario.infrastructure.persistence.repositories.producto import (
    SqlAlchemyProductoRepository,
)
from app.modules.ventas.infrastructure.adapters.inventario_port_impl import InventarioPortImpl
from app.modules.ventas.infrastructure.adapters.promociones_port_impl import PromocionesPortImpl
from app.modules.ventas.infrastructure.adapters.event_port_impl import EventPortImpl
from app.modules.sucursales.infrastructure.persistence.sucursal_repository_impl import (
    SqlAlchemySucursalRepository,
)

router = APIRouter(route_class=EnvelopeRoute)
caja_router = APIRouter(route_class=EnvelopeRoute)

_ORDEN_VENTAS = make_sort_dependency({"created_at"}, "created_at:desc")
_INC_VENTAS = make_include_dependency({"cliente", "usuario", "caja_turno"})


# --------------------------------------------------------------------------- #
# Mapeo de excepciones de dominio -> HTTP
# --------------------------------------------------------------------------- #
_NOT_FOUND = (vexc.VentaNoEncontrada, vexc.TurnoNoEncontrado, ClienteNoEncontrado, ProductoNoEncontrado)
_CONFLICT = (
    vexc.VentaYaCancelada, vexc.TurnoYaAbierto, vexc.TurnoYaCerrado,
    vexc.SucursalNoOperativa,
)
_FORBIDDEN = (vexc.AnulacionNoPermitida, vexc.CierreTurnoNoPermitido)
_BAD_REQUEST = (
    vexc.CajaNoAbierta, vexc.VentaCreditoSinCliente, vexc.VentaSinLineas,
    vexc.TurnoDeOtraSucursal, LimiteCreditoExcedido, StockInsuficiente,
    CantidadNoVendible, LoteRequerido, LoteInvalido, ValueError,
    vexc.VentaNoDevolvible, vexc.CantidadDevolucionExcedida, vexc.DevolucionInvalida,
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
        sucursal_repo=SqlAlchemySucursalRepository(db),
        promociones=PromocionesPortImpl(db),
    )


def _anular_use_case(db: AsyncSession) -> AnularVentaUseCase:
    return AnularVentaUseCase(
        venta_repo=SqlAlchemyVentaRepository(db),
        caja_repo=SqlAlchemyCajaTurnoRepository(db),
        inventario=InventarioPortImpl(db),
        cliente_repo=SqlAlchemyClienteRepository(db),
        event_port=EventPortImpl(db),
        devolucion_repo=SqlAlchemyDevolucionRepository(db),
    )


def _devolver_use_case(db: AsyncSession) -> DevolverVentaUseCase:
    return DevolverVentaUseCase(
        venta_repo=SqlAlchemyVentaRepository(db),
        devolucion_repo=SqlAlchemyDevolucionRepository(db),
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
        pagos=[
            PagoInput(monto=p.monto, metodo_pago=p.metodo_pago,
                      monto_recibido=p.monto_recibido)
            for p in body.pagos
        ],
        idempotency_key=idempotency_key,
    )
    try:
        venta = await _venta_use_case(db).ejecutar(entrada)
    except Exception as e:
        raise _traducir(e)
    return ok(venta)


@router.post("/cotizar", response_model=ApiResponse[CotizacionResponse])
async def cotizar_venta(
    body: CotizarVentaRequest,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("ventas.crear")),
):
    """Previsualiza el total con mayoreo y promociones aplicados, sin turno,
    sin pagos y sin tocar stock. Para mostrar el precio final en el POS."""
    sucursal_id = _exige_sucursal(actual)
    entrada = CotizarVentaInput(
        sucursal_id=sucursal_id,
        descuento_total=body.descuento_total,
        lineas=[
            LineaInput(
                producto_id=l.producto_id, cantidad=l.cantidad,
                precio_unitario=l.precio_unitario, descuento_linea=l.descuento_linea,
                impuesto_tasa=l.impuesto_tasa, producto_unidad_id=l.producto_unidad_id,
            ) for l in body.lineas
        ],
    )
    try:
        cotizacion = await _venta_use_case(db).cotizar(entrada)
    except Exception as e:
        raise _traducir(e)
    return ok(cotizacion)


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


@router.post(
    "/{venta_id}/devolucion", response_model=ApiResponse[DevolucionResponse],
    status_code=status.HTTP_201_CREATED,
)
async def devolver_venta(
    venta_id: UUID,
    body: DevolverVentaRequest,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("ventas.devolver")),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    try:
        existente = await ObtenerVentaUseCase(SqlAlchemyVentaRepository(db)).ejecutar(venta_id)
        verificar_alcance_sucursal(actual, existente.sucursal_id)
        devolucion = await _devolver_use_case(db).ejecutar(DevolverVentaInput(
            venta_id=venta_id,
            caja_turno_id=body.caja_turno_id,
            usuario_id=actual.id,
            metodo_devolucion=body.metodo_devolucion,
            lineas=[
                DevolverVentaLineaInput(detalle_venta_id=l.detalle_venta_id, cantidad=l.cantidad)
                for l in body.lineas
            ],
            motivo=body.motivo,
            puede_turno_cerrado=actual.ve_todas_las_sucursales,
            idempotency_key=idempotency_key,
        ))
    except HTTPException:
        raise
    except Exception as e:
        raise _traducir(e)
    return ok(devolucion)


@router.get("/{venta_id}/devoluciones", response_model=ApiResponse[list[DevolucionResponse]])
async def listar_devoluciones(
    venta_id: UUID,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("ventas.leer")),
):
    try:
        existente = await ObtenerVentaUseCase(SqlAlchemyVentaRepository(db)).ejecutar(venta_id)
    except Exception as e:
        raise _traducir(e)
    verificar_alcance_sucursal(actual, existente.sucursal_id)
    devoluciones = await SqlAlchemyDevolucionRepository(db).listar_por_venta(venta_id)
    return ok(devoluciones)


@router.get("/{venta_id}/ticket")
async def ticket_pdf(
    venta_id: UUID,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("ventas.leer")),
):
    """PDF del ticket de la venta (`application/pdf`, `inline` para pintarlo en la
    app). Ancho ~80 mm, listo para impresora térmica."""
    try:
        data = await GenerarTicketUseCase(
            SqlAlchemyVentaRepository(db),
            SqlAlchemyProductoRepository(db),
            SqlAlchemySucursalRepository(db),
        ).ejecutar(venta_id)
    except Exception as e:
        raise _traducir(e)
    verificar_alcance_sucursal(actual, data.sucursal_id)
    pdf = render_ticket_pdf(data)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="ticket-{data.folio}.pdf"'},
    )


# ========================================================================== #
# CAJA
# ========================================================================== #
@caja_router.post(
    "/abrir", response_model=ApiResponse[CajaTurnoResponse], status_code=status.HTTP_201_CREATED,
)
async def abrir_turno(
    body: AbrirCajaTurnoRequest,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("caja.operar", "ventas.crear")),
):
    sucursal_id = _exige_sucursal(actual)
    try:
        turno = await AbrirCajaTurnoUseCase(
            SqlAlchemyCajaTurnoRepository(db), EventPortImpl(db),
            SqlAlchemySucursalRepository(db),
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
    actual: UsuarioAutenticado = Depends(require_permission("caja.operar", "ventas.crear")),
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
    actual: UsuarioAutenticado = Depends(require_permission("caja.operar", "ventas.leer")),
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
    actual: UsuarioAutenticado = Depends(require_permission("caja.operar", "ventas.leer")),
):
    try:
        resumen = await ObtenerResumenTurnoUseCase(SqlAlchemyCajaTurnoRepository(db)).ejecutar(turno_id)
    except Exception as e:
        raise _traducir(e)
    verificar_alcance_sucursal(actual, resumen.turno.sucursal_id)
    return ok(ResumenTurnoResponse(
        turno=CajaTurnoResponse.model_validate(resumen.turno),
        total_efectivo=resumen.total_efectivo,
        total_devoluciones_efectivo=resumen.total_devoluciones_efectivo,
        cantidad_ventas=resumen.cantidad_ventas,
        saldo_esperado=resumen.saldo_esperado,
    ))
