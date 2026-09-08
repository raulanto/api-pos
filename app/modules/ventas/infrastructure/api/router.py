from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import (
    require_permission, UsuarioAutenticado, sucursal_scope, verificar_alcance_sucursal,
)
from app.shared.responses import (
    ApiResponse, EnvelopeRoute, PageParams, Sort,
    page_params, make_sort_dependency, make_include_dependency, ok, page_response,
)
from app.shared.filtering import active_filters
from app.modules.ventas.application.dtos import FiltroVentas, FiltroTurnos
from app.modules.ventas.domain.value_objects import EstadoVenta
from app.modules.ventas.domain import exceptions as vexc
from app.modules.clientes.domain.exceptions import (
    LimiteCreditoExcedido, ClienteNoEncontrado,
    SaldoMonederoInsuficiente, MovimientoMonederoInvalido,
)
from app.modules.inventario.domain.exceptions import (
    StockInsuficiente, ProductoNoEncontrado, CantidadNoVendible,
    LoteRequerido, LoteInvalido,
)
from app.modules.promociones.domain.exceptions import (
    CuponNoEncontrado, CuponVencido, CuponAgotado,
)
from app.modules.promociones.application.use_cases.validar_cupon import ValidarCuponUseCase
from app.modules.promociones.infrastructure.persistence.cupon_repository_impl import (
    SqlAlchemyCuponRepository,
)
from app.modules.ventas.infrastructure.api.schemas import (
    CrearVentaRequest, AnularVentaRequest, VentaResponse, VentaListItem,
    CotizarVentaRequest, CotizacionResponse,
    DevolverVentaRequest, DevolucionResponse,
    CuponValidarRequest, CuponValidacionResponse,
    AbrirCajaTurnoRequest, CerrarCajaTurnoRequest, CajaTurnoResponse, ResumenTurnoResponse,
    CajaCreateRequest, CajaRenameRequest, CajaResponse,
    MovimientoCajaRequest, MovimientoCajaResponse, ConciliarTurnoRequest,
    DenominacionResponse, TurnoListItem, EfectivoSucursalResponse,
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
    RegistrarMovimientoCajaUseCase, RegistrarMovimientoCajaInput,
    ListarMovimientosCajaUseCase, ConciliarTurnoUseCase, ConciliarTurnoInput,
    ListarTurnosUseCase, EfectivoEnSucursalUseCase,
)
from app.modules.ventas.application.use_cases.gestionar_terminales import (
    CrearCajaUseCase, CrearCajaInput, ListarCajasUseCase,
    RenombrarCajaUseCase, DesactivarCajaUseCase, ReactivarCajaUseCase,
    NombreCajaEnUso,
)
from app.modules.ventas.domain.entities import DenominacionConteo
from app.modules.ventas.application.use_cases.listar_ventas import (
    ListarVentasUseCase, ObtenerVentaUseCase,
)
from app.modules.ventas.application.use_cases.generar_ticket import GenerarTicketUseCase
from app.modules.ventas.infrastructure.pdf.ticket_pdf import render_ticket_pdf
from app.modules.ventas.infrastructure.persistence.repositories_impl import (
    SqlAlchemyVentaRepository, SqlAlchemyCajaTurnoRepository, SqlAlchemyCajaRepository,
    SqlAlchemyDevolucionRepository,
)
from app.modules.clientes.infrastructure.persistence.cliente_repository_impl import (
    SqlAlchemyClienteRepository,
)
from app.modules.inventario.infrastructure.persistence.repositories.producto import (
    SqlAlchemyProductoRepository,
)
from app.modules.ventas.infrastructure.adapters.inventario_port_impl import InventarioPortImpl
from app.modules.ventas.infrastructure.adapters.promociones_port_impl import PromocionesPortImpl
from app.modules.ventas.infrastructure.adapters.descuento_config_port_impl import (
    DescuentoConfigPortImpl,
)
from app.modules.ventas.infrastructure.adapters.monedero_port_impl import MonederoPortImpl
from app.modules.ventas.infrastructure.adapters.event_port_impl import EventPortImpl
from app.modules.sucursales.infrastructure.persistence.sucursal_repository_impl import (
    SqlAlchemySucursalRepository,
)

router = APIRouter(route_class=EnvelopeRoute)
caja_router = APIRouter(route_class=EnvelopeRoute)
cajas_router = APIRouter(route_class=EnvelopeRoute)

_ORDEN_VENTAS = make_sort_dependency({"created_at"}, "created_at:desc")
_INC_VENTAS = make_include_dependency({"cliente", "usuario", "caja_turno"})
_ORDEN_TURNOS = make_sort_dependency({"abierto_en", "cerrado_en"}, "abierto_en:desc")


# --------------------------------------------------------------------------- #
# Mapeo de excepciones de dominio -> HTTP
# --------------------------------------------------------------------------- #
_NOT_FOUND = (
    vexc.VentaNoEncontrada, vexc.TurnoNoEncontrado, ClienteNoEncontrado,
    ProductoNoEncontrado, CuponNoEncontrado, vexc.CajaNoEncontrada,
)
_CONFLICT = (
    vexc.VentaYaCancelada, vexc.TurnoYaAbierto, vexc.TurnoYaCerrado,
    vexc.SucursalNoOperativa, CuponAgotado, vexc.CajaInactiva,
    vexc.TurnoNoRequiereConciliacion, vexc.MovimientoTurnoCerrado, NombreCajaEnUso,
)
_FORBIDDEN = (
    vexc.AnulacionNoPermitida, vexc.CierreTurnoNoPermitido,
    vexc.DescuentoManualNoAutorizado, vexc.ConciliacionNoPermitida,
)
_BAD_REQUEST = (
    vexc.CajaNoAbierta, vexc.VentaCreditoSinCliente, vexc.VentaSinLineas,
    vexc.TurnoDeOtraSucursal, LimiteCreditoExcedido, StockInsuficiente,
    CantidadNoVendible, LoteRequerido, LoteInvalido, ValueError,
    vexc.VentaNoDevolvible, vexc.CantidadDevolucionExcedida, vexc.DevolucionInvalida,
    SaldoMonederoInsuficiente, MovimientoMonederoInvalido, CuponVencido,
    vexc.DescuentoManualExcedeTope, vexc.MotivoDescuentoRequerido,
    vexc.NotaCierreRequerida, vexc.MotivoMovimientoRequerido, vexc.DenominacionNoCuadra,
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


def _denominacion(d) -> DenominacionConteo:
    return DenominacionConteo(valor=d.valor, cantidad=d.cantidad)


def _venta_use_case(db: AsyncSession) -> CrearVentaUseCase:
    return CrearVentaUseCase(
        venta_repo=SqlAlchemyVentaRepository(db),
        caja_repo=SqlAlchemyCajaTurnoRepository(db),
        inventario=InventarioPortImpl(db),
        cliente_repo=SqlAlchemyClienteRepository(db),
        event_port=EventPortImpl(db),
        sucursal_repo=SqlAlchemySucursalRepository(db),
        promociones=PromocionesPortImpl(db),
        monedero=MonederoPortImpl(db),
        descuento_config=DescuentoConfigPortImpl(db),
    )


def _anular_use_case(db: AsyncSession) -> AnularVentaUseCase:
    return AnularVentaUseCase(
        venta_repo=SqlAlchemyVentaRepository(db),
        caja_repo=SqlAlchemyCajaTurnoRepository(db),
        inventario=InventarioPortImpl(db),
        cliente_repo=SqlAlchemyClienteRepository(db),
        event_port=EventPortImpl(db),
        devolucion_repo=SqlAlchemyDevolucionRepository(db),
        monedero=MonederoPortImpl(db),
        promociones=PromocionesPortImpl(db),
    )


def _devolver_use_case(db: AsyncSession) -> DevolverVentaUseCase:
    return DevolverVentaUseCase(
        venta_repo=SqlAlchemyVentaRepository(db),
        devolucion_repo=SqlAlchemyDevolucionRepository(db),
        caja_repo=SqlAlchemyCajaTurnoRepository(db),
        inventario=InventarioPortImpl(db),
        cliente_repo=SqlAlchemyClienteRepository(db),
        event_port=EventPortImpl(db),
        monedero=MonederoPortImpl(db),
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
        telefono=body.telefono,
        motivo_descuento=body.motivo_descuento,
        puede_descuento_manual=actual.tiene_permiso("ventas.descuento_manual"),
        rol_id=actual.rol_id,
        codigo_cupon=body.codigo_cupon,
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
        metodos_pago=frozenset(body.metodos_pago),
        cliente_segmento=body.cliente_segmento,
        codigo_cupon=body.codigo_cupon,
        telefono=body.telefono,
    )
    try:
        cotizacion = await _venta_use_case(db).cotizar(entrada)
    except Exception as e:
        raise _traducir(e)
    return ok(cotizacion)


@router.post("/cupon/validar", response_model=ApiResponse[CuponValidacionResponse])
async def validar_cupon(
    body: CuponValidarRequest,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("ventas.crear")),
):
    """Previsualiza un código de cupón: devuelve la `promocion_id` que habilita
    (o el error si está vencido/agotado). No consume el cupón."""
    try:
        pid = await ValidarCuponUseCase(SqlAlchemyCuponRepository(db)).ejecutar(
            body.codigo, telefono=body.telefono, cliente_id=body.cliente_id,
        )
    except Exception as e:
        raise _traducir(e)
    return ok(CuponValidacionResponse(promocion_id=pid))


@router.get("/", response_model=ApiResponse[list[VentaListItem]])
async def listar_ventas(
    request: Request,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("ventas.leer")),
    sucursal_id: UUID | None = Query(default=None),
    caja_turno_id: UUID | None = Query(default=None),
    cliente_id: UUID | None = Query(default=None),
    telefono: str | None = Query(default=None, description="Historial de compras por teléfono"),
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
        telefono=telefono, estado=estado, desde=desde, hasta=hasta,
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
# CAJAS FÍSICAS (terminales) — /api/v1/cajas
# ========================================================================== #
@cajas_router.post(
    "/", response_model=ApiResponse[CajaResponse], status_code=status.HTTP_201_CREATED,
)
async def crear_caja(
    body: CajaCreateRequest,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("caja.administrar")),
):
    sucursal_id = _exige_sucursal(actual)
    try:
        caja = await CrearCajaUseCase(SqlAlchemyCajaRepository(db)).ejecutar(
            CrearCajaInput(sucursal_id=sucursal_id, nombre=body.nombre)
        )
    except Exception as e:
        raise _traducir(e)
    return ok(caja)


@cajas_router.get("/", response_model=ApiResponse[list[CajaResponse]])
async def listar_cajas(
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("caja.operar", "caja.administrar")),
    sucursal_id: UUID | None = Query(default=None),
    incluir_inactivas: bool = Query(default=False),
):
    efectiva = _sucursal_efectiva(actual, sucursal_id) or _exige_sucursal(actual)
    cajas = await ListarCajasUseCase(SqlAlchemyCajaRepository(db)).ejecutar(
        efectiva, incluir_inactivas,
    )
    return ok(cajas)


@cajas_router.patch("/{caja_id}", response_model=ApiResponse[CajaResponse])
async def renombrar_caja(
    caja_id: UUID,
    body: CajaRenameRequest,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("caja.administrar")),
):
    try:
        caja = await RenombrarCajaUseCase(SqlAlchemyCajaRepository(db)).ejecutar(
            caja_id, body.nombre,
        )
        verificar_alcance_sucursal(actual, caja.sucursal_id)
    except HTTPException:
        raise
    except Exception as e:
        raise _traducir(e)
    return ok(caja)


@cajas_router.delete("/{caja_id}", response_model=ApiResponse[CajaResponse])
async def desactivar_caja(
    caja_id: UUID,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("caja.administrar")),
):
    try:
        caja = await DesactivarCajaUseCase(SqlAlchemyCajaRepository(db)).ejecutar(caja_id)
        verificar_alcance_sucursal(actual, caja.sucursal_id)
    except HTTPException:
        raise
    except Exception as e:
        raise _traducir(e)
    return ok(caja)


@cajas_router.patch("/{caja_id}/reactivar", response_model=ApiResponse[CajaResponse])
async def reactivar_caja(
    caja_id: UUID,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("caja.administrar")),
):
    try:
        caja = await ReactivarCajaUseCase(SqlAlchemyCajaRepository(db)).ejecutar(caja_id)
        verificar_alcance_sucursal(actual, caja.sucursal_id)
    except HTTPException:
        raise
    except Exception as e:
        raise _traducir(e)
    return ok(caja)


# ========================================================================== #
# CAJA — turnos, movimientos, arqueo — /api/v1/caja-turnos
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
            SqlAlchemySucursalRepository(db), SqlAlchemyCajaRepository(db),
        ).ejecutar(AbrirCajaTurnoInput(
            sucursal_id=sucursal_id, caja_id=body.caja_id, usuario_id=actual.id,
            saldo_inicial=body.saldo_inicial,
            denominaciones=[
                _denominacion(d) for d in body.denominaciones
            ] or None,
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


@caja_router.get("/historico", response_model=ApiResponse[list[TurnoListItem]])
async def historico_turnos(
    request: Request,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("caja.ver_historico")),
    sucursal_id: UUID | None = Query(default=None),
    caja_id: UUID | None = Query(default=None),
    usuario_id: UUID | None = Query(default=None, description="Diferencias por cajero"),
    estado: str | None = Query(default=None),
    desde: datetime | None = Query(default=None),
    hasta: datetime | None = Query(default=None),
    paginacion: PageParams = Depends(page_params),
    orden: Sort = Depends(_ORDEN_TURNOS),
):
    efectiva = _sucursal_efectiva(actual, sucursal_id)
    filtro = FiltroTurnos(
        sucursal_id=efectiva, caja_id=caja_id, usuario_id=usuario_id,
        estado=estado, desde=desde, hasta=hasta,
    )
    pagina = await ListarTurnosUseCase(SqlAlchemyCajaTurnoRepository(db)).ejecutar(
        filtro, paginacion, orden,
    )
    pagina.items = [TurnoListItem.model_validate(t) for t in pagina.items]
    return page_response(
        request, pagina, paginacion, sort=orden, filters=active_filters(filtro),
    )


@caja_router.get("/efectivo-actual", response_model=ApiResponse[EfectivoSucursalResponse])
async def efectivo_actual(
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("caja.ver_historico")),
    sucursal_id: UUID | None = Query(default=None),
):
    efectiva = _sucursal_efectiva(actual, sucursal_id) or _exige_sucursal(actual)
    total = await EfectivoEnSucursalUseCase(SqlAlchemyCajaTurnoRepository(db)).ejecutar(efectiva)
    return ok(EfectivoSucursalResponse(sucursal_id=efectiva, efectivo_esperado=total))


@caja_router.post("/{turno_id}/cerrar", response_model=ApiResponse[CajaTurnoResponse])
async def cerrar_turno(
    turno_id: UUID,
    body: CerrarCajaTurnoRequest,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("caja.operar", "ventas.crear")),
):
    try:
        turno = await CerrarCajaTurnoUseCase(
            SqlAlchemyCajaTurnoRepository(db), EventPortImpl(db),
            umbral=settings.caja_diferencia_umbral,
        ).ejecutar(CerrarCajaTurnoInput(
            caja_turno_id=turno_id,
            usuario_id=actual.id,
            saldo_final_declarado=body.saldo_final_declarado,
            nota_cierre=body.nota_cierre,
            denominaciones=[_denominacion(d) for d in body.denominaciones] or None,
            puede_cerrar_ajeno=actual.tiene_permiso("caja.forzar_cierre"),
        ))
    except Exception as e:
        raise _traducir(e)
    return ok(turno)


@caja_router.post(
    "/{turno_id}/movimientos", response_model=ApiResponse[MovimientoCajaResponse],
    status_code=status.HTTP_201_CREATED,
)
async def registrar_movimiento(
    turno_id: UUID,
    body: MovimientoCajaRequest,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("caja.operar")),
):
    try:
        mov = await RegistrarMovimientoCajaUseCase(
            SqlAlchemyCajaTurnoRepository(db), EventPortImpl(db),
        ).ejecutar(RegistrarMovimientoCajaInput(
            caja_turno_id=turno_id,
            usuario_id=actual.id,
            tipo=body.tipo,
            monto=body.monto,
            motivo=body.motivo,
            puede_operar_ajeno=actual.tiene_permiso("caja.forzar_cierre"),
        ))
    except Exception as e:
        raise _traducir(e)
    return ok(mov)


@caja_router.get(
    "/{turno_id}/movimientos", response_model=ApiResponse[list[MovimientoCajaResponse]],
)
async def listar_movimientos(
    turno_id: UUID,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("caja.operar", "ventas.leer")),
):
    try:
        movs = await ListarMovimientosCajaUseCase(SqlAlchemyCajaTurnoRepository(db)).ejecutar(turno_id)
    except Exception as e:
        raise _traducir(e)
    return ok(movs)


@caja_router.post("/{turno_id}/conciliar", response_model=ApiResponse[CajaTurnoResponse])
async def conciliar_turno(
    turno_id: UUID,
    body: ConciliarTurnoRequest,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("caja.autorizar_diferencia")),
):
    try:
        turno = await ConciliarTurnoUseCase(
            SqlAlchemyCajaTurnoRepository(db), EventPortImpl(db),
        ).ejecutar(ConciliarTurnoInput(
            caja_turno_id=turno_id,
            usuario_id=actual.id,
            puede_conciliar=actual.tiene_permiso("caja.autorizar_diferencia"),
            nota=body.nota,
        ))
        verificar_alcance_sucursal(actual, turno.sucursal_id)
    except HTTPException:
        raise
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
        total_ingresos=resumen.total_ingresos,
        total_retiros=resumen.total_retiros,
        total_gastos=resumen.total_gastos,
        movimientos_neto=resumen.movimientos_neto,
        saldo_esperado=resumen.saldo_esperado,
        denominaciones_apertura=[
            DenominacionResponse(valor=d.valor, cantidad=d.cantidad)
            for d in resumen.denominaciones_apertura
        ],
        denominaciones_cierre=[
            DenominacionResponse(valor=d.valor, cantidad=d.cantidad)
            for d in resumen.denominaciones_cierre
        ],
    ))
