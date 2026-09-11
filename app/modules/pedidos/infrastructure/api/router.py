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
    page_params, make_sort_dependency, ok, page_response,
)
from app.shared.filtering import active_filters

from app.modules.ventas.infrastructure.api.router import (
    _venta_use_case as _crear_venta_uc, _traducir as _traducir_venta,
)
from app.modules.ventas.infrastructure.adapters.event_port_impl import EventPortImpl
from app.modules.ventas.infrastructure.persistence.repositories_impl import (
    SqlAlchemyVentaRepository,
)
from app.modules.ventas.application.use_cases.crear_venta import PagoInput
from app.modules.ventas.infrastructure.api.schemas import VentaResponse

from app.modules.pedidos.application.dtos import FiltroPedidos
from app.modules.pedidos.domain.value_objects import EstadoPedido, EstadoEntrega, TipoPedido, CanalPedido
from app.modules.pedidos.domain import exceptions as pexc
from app.modules.usuarios.infrastructure.persistence.usuario_repository_impl import (
    SqlAlchemyUsuarioRepository,
)
from app.modules.pedidos.infrastructure.persistence.repositories_impl import (
    SqlAlchemyPedidoRepository,
)
from app.modules.pedidos.infrastructure.api.schemas import (
    CrearPedidoRequest, ActualizarPedidoRequest, CancelarPedidoRequest,
    CambiarEntregaRequest, RegistrarAnticipoRequest, FacturarPedidoRequest,
    AsignarServiciosRequest,
    PedidoResponse, PedidoListItem, PedidoPagoResponse, ResumenPedidosResponse,
)
from app.modules.pedidos.application.use_cases.crear_pedido import (
    CrearPedidoUseCase, CrearPedidoInput, LineaPedidoInput,
)
from app.modules.pedidos.application.use_cases.actualizar_pedido import (
    ActualizarPedidoUseCase, ActualizarPedidoInput, _SIN_CAMBIO,
)
from app.modules.pedidos.application.use_cases.gestionar_pedido import (
    ConfirmarPedidoUseCase, ReabrirPedidoUseCase, CancelarPedidoUseCase,
    CambiarEntregaUseCase, CambiarEntregaInput,
    RegistrarAnticipoUseCase, RegistrarAnticipoInput,
    AsignarServiciosUseCase, AsignarServiciosInput,
)
from app.modules.pedidos.application.use_cases.facturar_pedido import (
    FacturarPedidoUseCase, FacturarPedidoInput,
)
from app.modules.pedidos.application.use_cases.listar_pedidos import (
    ListarPedidosUseCase, ObtenerPedidoUseCase, ResumenPedidosUseCase,
)

router = APIRouter(route_class=EnvelopeRoute)

_ORDEN = make_sort_dependency({"created_at", "fecha_promesa"}, "created_at:desc")


# --------------------------------------------------------------------------- #
_NOT_FOUND = (pexc.PedidoNoEncontrado,)
_CONFLICT = (pexc.PedidoYaFacturado, pexc.TransicionPedidoInvalida, pexc.EntregaNoAplica)
_BAD_REQUEST = (
    pexc.PedidoSinLineas, pexc.PedidoNoEditable, pexc.DireccionEnvioRequerida,
    pexc.AnticipoInvalido, pexc.MotivoDescuentoRequerido,
    pexc.ServicioSinResponsable, pexc.ResponsableInvalido,
)


def _traducir(error: Exception) -> HTTPException:
    if isinstance(error, _NOT_FOUND):
        return HTTPException(status.HTTP_404_NOT_FOUND, detail=str(error))
    if isinstance(error, _CONFLICT):
        return HTTPException(status.HTTP_409_CONFLICT, detail=str(error))
    if isinstance(error, _BAD_REQUEST):
        return HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(error))
    # Errores que puede levantar CrearVentaUseCase al facturar (stock, caja,
    # crédito, sucursal no operativa, ...): los mapea el traductor de ventas.
    return _traducir_venta(error)


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


def _repo(db: AsyncSession) -> SqlAlchemyPedidoRepository:
    return SqlAlchemyPedidoRepository(db)


def _lineas_input(lineas) -> list[LineaPedidoInput]:
    return [
        LineaPedidoInput(
            producto_id=l.producto_id, cantidad=l.cantidad,
            precio_unitario=l.precio_unitario, descuento_linea=l.descuento_linea,
            impuesto_tasa=l.impuesto_tasa, producto_unidad_id=l.producto_unidad_id,
            asignado_a=l.asignado_a,
        ) for l in lineas
    ]


# ========================================================================== #
@router.post("/", response_model=ApiResponse[PedidoResponse], status_code=status.HTTP_201_CREATED)
async def crear_pedido(
    body: CrearPedidoRequest,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("pedidos.crear")),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    sucursal_id = _exige_sucursal(actual)
    uc = CrearPedidoUseCase(
        _repo(db), _crear_venta_uc(db), EventPortImpl(db), SqlAlchemyUsuarioRepository(db),
    )
    try:
        pedido = await uc.ejecutar(CrearPedidoInput(
            sucursal_id=sucursal_id, usuario_id=actual.id,
            tipo=body.tipo, canal=body.canal, lineas=_lineas_input(body.lineas),
            cliente_id=body.cliente_id, telefono=body.telefono,
            descuento_total=body.descuento_total, motivo_descuento=body.motivo_descuento,
            codigo_cupon=body.codigo_cupon,
            cliente_segmento=body.cliente_segmento, notas=body.notas,
            fecha_promesa=body.fecha_promesa,
            direccion_texto=body.direccion_texto,
            referencia_direccion=body.referencia_direccion,
            idempotency_key=idempotency_key, confirmar=body.confirmar,
        ))
    except Exception as e:
        raise _traducir(e)
    return ok(PedidoResponse.model_validate(pedido))


@router.get("/", response_model=ApiResponse[list[PedidoListItem]])
async def listar_pedidos(
    request: Request,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("pedidos.leer")),
    sucursal_id: UUID | None = Query(default=None),
    cliente_id: UUID | None = Query(default=None),
    repartidor_id: UUID | None = Query(default=None),
    telefono: str | None = Query(default=None),
    tipo: TipoPedido | None = Query(default=None),
    canal: CanalPedido | None = Query(default=None),
    estado: EstadoPedido | None = Query(default=None),
    estado_entrega: EstadoEntrega | None = Query(default=None),
    desde: datetime | None = Query(default=None),
    hasta: datetime | None = Query(default=None),
    paginacion: PageParams = Depends(page_params),
    orden: Sort = Depends(_ORDEN),
):
    filtro = FiltroPedidos(
        sucursal_id=_sucursal_efectiva(actual, sucursal_id), cliente_id=cliente_id,
        repartidor_id=repartidor_id, telefono=telefono, tipo=tipo, canal=canal,
        estado=estado, estado_entrega=estado_entrega, desde=desde, hasta=hasta,
    )
    pagina = await ListarPedidosUseCase(_repo(db)).ejecutar(filtro, paginacion, orden)
    pagina.items = [PedidoListItem.model_validate(p) for p in pagina.items]
    return page_response(
        request, pagina, paginacion, sort=orden, filters=active_filters(filtro),
    )


@router.get("/resumen", response_model=ApiResponse[ResumenPedidosResponse])
async def resumen_pedidos(
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("pedidos.leer")),
    sucursal_id: UUID | None = Query(default=None),
):
    efectiva = _sucursal_efectiva(actual, sucursal_id) or _exige_sucursal(actual)
    res = await ResumenPedidosUseCase(_repo(db)).ejecutar(efectiva)
    return ok(ResumenPedidosResponse(**res))


@router.get("/{pedido_id}", response_model=ApiResponse[PedidoResponse])
async def obtener_pedido(
    pedido_id: UUID,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("pedidos.leer")),
):
    try:
        pedido = await ObtenerPedidoUseCase(_repo(db)).ejecutar(pedido_id)
    except Exception as e:
        raise _traducir(e)
    verificar_alcance_sucursal(actual, pedido.sucursal_id)
    return ok(PedidoResponse.model_validate(pedido))


@router.patch("/{pedido_id}", response_model=ApiResponse[PedidoResponse])
async def actualizar_pedido(
    pedido_id: UUID,
    body: ActualizarPedidoRequest,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("pedidos.editar")),
):
    puestos = body.model_fields_set
    campos = [
        "tipo", "canal", "cliente_id", "telefono", "descuento_total", "motivo_descuento",
        "codigo_cupon", "cliente_segmento", "notas", "fecha_promesa",
        "direccion_texto", "referencia_direccion",
    ]
    kwargs = {c: (getattr(body, c) if c in puestos else _SIN_CAMBIO) for c in campos}
    lineas = _lineas_input(body.lineas) if ("lineas" in puestos and body.lineas) else None
    try:
        pedido = await ActualizarPedidoUseCase(
            _repo(db), _crear_venta_uc(db), SqlAlchemyUsuarioRepository(db),
        ).ejecutar(
            ActualizarPedidoInput(pedido_id=pedido_id, lineas=lineas, **kwargs)
        )
    except HTTPException:
        raise
    except Exception as e:
        raise _traducir(e)
    verificar_alcance_sucursal(actual, pedido.sucursal_id)
    return ok(PedidoResponse.model_validate(pedido))


@router.post("/{pedido_id}/confirmar", response_model=ApiResponse[PedidoResponse])
async def confirmar_pedido(
    pedido_id: UUID,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("pedidos.confirmar")),
):
    try:
        pedido = await ConfirmarPedidoUseCase(
            _repo(db), _crear_venta_uc(db), EventPortImpl(db),
        ).ejecutar(pedido_id, actual.id)
    except Exception as e:
        raise _traducir(e)
    verificar_alcance_sucursal(actual, pedido.sucursal_id)
    return ok(PedidoResponse.model_validate(pedido))


@router.post("/{pedido_id}/reabrir", response_model=ApiResponse[PedidoResponse])
async def reabrir_pedido(
    pedido_id: UUID,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("pedidos.editar")),
):
    try:
        pedido = await ReabrirPedidoUseCase(_repo(db), EventPortImpl(db)).ejecutar(
            pedido_id, actual.id,
        )
    except Exception as e:
        raise _traducir(e)
    verificar_alcance_sucursal(actual, pedido.sucursal_id)
    return ok(PedidoResponse.model_validate(pedido))


@router.post("/{pedido_id}/cancelar", response_model=ApiResponse[PedidoResponse])
async def cancelar_pedido(
    pedido_id: UUID,
    body: CancelarPedidoRequest,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("pedidos.cancelar")),
):
    try:
        pedido = await CancelarPedidoUseCase(_repo(db), EventPortImpl(db)).ejecutar(
            pedido_id, actual.id, motivo=body.motivo,
        )
    except Exception as e:
        raise _traducir(e)
    verificar_alcance_sucursal(actual, pedido.sucursal_id)
    return ok(PedidoResponse.model_validate(pedido))


@router.patch("/{pedido_id}/entrega", response_model=ApiResponse[PedidoResponse])
async def cambiar_entrega(
    pedido_id: UUID,
    body: CambiarEntregaRequest,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("pedidos.repartir")),
):
    try:
        pedido = await CambiarEntregaUseCase(_repo(db), EventPortImpl(db)).ejecutar(
            CambiarEntregaInput(
                pedido_id=pedido_id, usuario_id=actual.id,
                estado_entrega=body.estado_entrega, repartidor_id=body.repartidor_id,
                motivo=body.motivo,
            )
        )
    except Exception as e:
        raise _traducir(e)
    verificar_alcance_sucursal(actual, pedido.sucursal_id)
    return ok(PedidoResponse.model_validate(pedido))


@router.post(
    "/{pedido_id}/anticipos", response_model=ApiResponse[PedidoPagoResponse],
    status_code=status.HTTP_201_CREATED,
)
async def registrar_anticipo(
    pedido_id: UUID,
    body: RegistrarAnticipoRequest,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("pedidos.editar")),
):
    try:
        pago = await RegistrarAnticipoUseCase(_repo(db), EventPortImpl(db)).ejecutar(
            RegistrarAnticipoInput(
                pedido_id=pedido_id, usuario_id=actual.id, monto=body.monto,
                metodo_pago=body.metodo_pago, referencia=body.referencia,
            )
        )
    except Exception as e:
        raise _traducir(e)
    return ok(PedidoPagoResponse.model_validate(pago))


@router.patch("/{pedido_id}/asignaciones", response_model=ApiResponse[PedidoResponse])
async def asignar_servicios(
    pedido_id: UUID,
    body: AsignarServiciosRequest,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("pedidos.editar")),
):
    """Fija/reasigna el responsable de líneas de servicio sin re-cotizar. Vale en
    borrador y confirmado."""
    try:
        pedido = await AsignarServiciosUseCase(
            _repo(db), EventPortImpl(db), SqlAlchemyUsuarioRepository(db),
        ).ejecutar(AsignarServiciosInput(
            pedido_id=pedido_id, usuario_id=actual.id,
            asignaciones=[(a.detalle_id, a.asignado_a) for a in body.asignaciones],
        ))
    except Exception as e:
        raise _traducir(e)
    verificar_alcance_sucursal(actual, pedido.sucursal_id)
    return ok(PedidoResponse.model_validate(pedido))


@router.post(
    "/{pedido_id}/facturar", response_model=ApiResponse[VentaResponse],
    status_code=status.HTTP_201_CREATED,
)
async def facturar_pedido(
    pedido_id: UUID,
    body: FacturarPedidoRequest,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("pedidos.facturar")),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    uc = FacturarPedidoUseCase(
        _repo(db), SqlAlchemyVentaRepository(db), _crear_venta_uc(db), EventPortImpl(db),
    )
    try:
        venta = await uc.ejecutar(FacturarPedidoInput(
            pedido_id=pedido_id, usuario_id=actual.id,
            caja_turno_id=body.caja_turno_id,
            pagos=[
                PagoInput(monto=p.monto, metodo_pago=p.metodo_pago,
                          monto_recibido=p.monto_recibido)
                for p in body.pagos
            ],
            recalcular_precios=body.recalcular_precios,
            puede_descuento_manual=actual.tiene_permiso("ventas.descuento_manual"),
            rol_id=actual.rol_id,
            idempotency_key=idempotency_key,
        ))
    except HTTPException:
        raise
    except Exception as e:
        raise _traducir(e)
    verificar_alcance_sucursal(actual, venta.sucursal_id)
    return ok(venta)
