from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.exc import IntegrityError
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

from app.modules.proveedores.domain import exceptions as pexc
from app.modules.proveedores.domain.value_objects import (
    EstadoPedidoProveedor, EstadoDevolucionProveedor,
)
from app.modules.proveedores.application.dtos import (
    FiltroProveedores, FiltroPedidosProveedor, FiltroRecepciones, FiltroDevoluciones,
)
from app.modules.proveedores.application.use_cases.gestionar_proveedor import (
    CrearProveedorUseCase, CrearProveedorInput, ActualizarProveedorUseCase,
    ActualizarProveedorInput, DesactivarProveedorUseCase, ReactivarProveedorUseCase,
    ObtenerProveedorUseCase, ListarProveedoresUseCase,
)
from app.modules.proveedores.application.use_cases.gestionar_producto_proveedor import (
    VincularProductoProveedorUseCase, VincularProductoProveedorInput,
    DesvincularProductoProveedorUseCase, MarcarProveedorPrincipalUseCase,
    ListarProductoProveedorPorProductoUseCase, ListarProductoProveedorPorProveedorUseCase,
)
from app.modules.proveedores.application.use_cases.gestionar_pedido_proveedor import (
    CrearPedidoProveedorUseCase, CrearPedidoProveedorInput, LineaPedidoProveedorInput,
    ConfirmarEnvioPedidoProveedorUseCase, CancelarPedidoProveedorUseCase,
    ObtenerPedidoProveedorUseCase, ListarPedidosProveedorUseCase,
)
from app.modules.proveedores.application.use_cases.evaluar_reorden import EvaluarReordenUseCase
from app.modules.proveedores.application.use_cases.registrar_recepcion import (
    RegistrarRecepcionUseCase, RegistrarRecepcionInput, LineaRecepcionInput,
    ObtenerRecepcionUseCase, ListarRecepcionesUseCase,
)
from app.modules.proveedores.application.use_cases.gestionar_devolucion import (
    CrearDevolucionUseCase, CrearDevolucionInput, LineaDevolucionInput,
    EnviarDevolucionUseCase, CerrarDevolucionUseCase, ObtenerDevolucionUseCase,
    ListarDevolucionesUseCase,
)
from app.modules.proveedores.application.use_cases.reportes_proveedor import ResumenProveedorUseCase

from app.modules.proveedores.infrastructure.persistence.repositories_impl import (
    SqlAlchemyProveedorRepository, SqlAlchemyProductoProveedorRepository,
    SqlAlchemyPedidoProveedorRepository, SqlAlchemyRecepcionProveedorRepository,
    SqlAlchemyDevolucionProveedorRepository,
)
from app.modules.proveedores.infrastructure.api.schemas import (
    ProveedorCreateRequest, ProveedorUpdateRequest, ProveedorResponse,
    ProductoProveedorCreateRequest, ProductoProveedorResponse,
    PedidoProveedorCreateRequest, PedidoProveedorResponse,
    RecepcionProveedorCreateRequest, RecepcionProveedorResponse,
    DevolucionProveedorCreateRequest, CerrarDevolucionRequest, DevolucionProveedorResponse,
    ReordenGeneradoResponse, ResumenProveedorResponse,
)

from app.modules.inventario.infrastructure.persistence.repositories import (
    SqlAlchemyProductoRepository, SqlAlchemyExistenciaRepository, SqlAlchemyMovimientoRepository,
)
from app.modules.inventario.application.use_cases.aplicar_movimiento import AplicarMovimientoUseCase
from app.modules.inventario.infrastructure.adapters.event_port_impl import EventPortImpl

router = APIRouter(route_class=EnvelopeRoute)

_ORDEN_PEDIDOS = make_sort_dependency({"fecha_pedido"}, "fecha_pedido:desc")


# --------------------------------------------------------------------------- #
_NOT_FOUND = (
    pexc.ProveedorNoEncontrado, pexc.ProductoProveedorNoEncontrado,
    pexc.PedidoProveedorNoEncontrado, pexc.RecepcionProveedorNoEncontrada,
    pexc.DevolucionProveedorNoEncontrada,
)
_CONFLICT = (
    pexc.CodigoProveedorEnUso, pexc.ProductoProveedorYaExiste, pexc.YaHayProveedorPrincipal,
)
_BAD_REQUEST = (
    pexc.DiasCreditoRequerido, pexc.PedidoProveedorSinLineas, pexc.PedidoNoEditable,
    pexc.TransicionPedidoProveedorInvalida, pexc.RecepcionSinLineas, pexc.DefectoInvalido,
    pexc.CantidadDevolucionExcedeDefecto, pexc.TransicionDevolucionInvalida, ValueError,
)


def _traducir(error: Exception) -> HTTPException:
    if isinstance(error, _NOT_FOUND):
        return HTTPException(status.HTTP_404_NOT_FOUND, detail=str(error))
    if isinstance(error, _CONFLICT):
        return HTTPException(status.HTTP_409_CONFLICT, detail=str(error))
    if isinstance(error, _BAD_REQUEST):
        return HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(error))
    raise error


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


def _prov_repo(db: AsyncSession) -> SqlAlchemyProveedorRepository:
    return SqlAlchemyProveedorRepository(db)


def _pp_repo(db: AsyncSession) -> SqlAlchemyProductoProveedorRepository:
    return SqlAlchemyProductoProveedorRepository(db)


def _pedido_repo(db: AsyncSession) -> SqlAlchemyPedidoProveedorRepository:
    return SqlAlchemyPedidoProveedorRepository(db)


def _recepcion_repo(db: AsyncSession) -> SqlAlchemyRecepcionProveedorRepository:
    return SqlAlchemyRecepcionProveedorRepository(db)


def _devolucion_repo(db: AsyncSession) -> SqlAlchemyDevolucionProveedorRepository:
    return SqlAlchemyDevolucionProveedorRepository(db)


def _aplicar_movimiento_uc(db: AsyncSession) -> AplicarMovimientoUseCase:
    return AplicarMovimientoUseCase(
        SqlAlchemyProductoRepository(db), SqlAlchemyExistenciaRepository(db),
        SqlAlchemyMovimientoRepository(db), EventPortImpl(db),
    )


# ========================================================================== #
# FASE 1 — Proveedor
# ========================================================================== #
@router.post(
    "", response_model=ApiResponse[ProveedorResponse], status_code=status.HTTP_201_CREATED,
)
async def crear_proveedor(
    body: ProveedorCreateRequest,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("proveedores.crear")),
):
    try:
        proveedor = await CrearProveedorUseCase(_prov_repo(db)).ejecutar(
            CrearProveedorInput(**body.model_dump())
        )
    except Exception as e:
        raise _traducir(e)
    return ok(proveedor)


@router.get("", response_model=ApiResponse[list[ProveedorResponse]])
async def listar_proveedores(
    request: Request,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("proveedores.leer")),
    activo: bool | None = Query(default=None),
    q: str | None = Query(default=None, description="Busca en código, razón social y RFC"),
    paginacion: PageParams = Depends(page_params),
    orden: Sort = Depends(make_sort_dependency({"razon_social", "codigo"}, "razon_social:asc")),
):
    filtro = FiltroProveedores(activo=activo, busqueda=q)
    pagina = await ListarProveedoresUseCase(_prov_repo(db)).ejecutar(filtro, paginacion, orden)
    pagina.items = [ProveedorResponse.model_validate(p) for p in pagina.items]
    return page_response(request, pagina, paginacion, sort=orden, filters=active_filters(filtro))


@router.get("/{proveedor_id}", response_model=ApiResponse[ProveedorResponse])
async def obtener_proveedor(
    proveedor_id: UUID,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("proveedores.leer")),
):
    try:
        proveedor = await ObtenerProveedorUseCase(_prov_repo(db)).ejecutar(proveedor_id)
    except Exception as e:
        raise _traducir(e)
    return ok(proveedor)


@router.patch("/{proveedor_id}", response_model=ApiResponse[ProveedorResponse])
async def actualizar_proveedor(
    proveedor_id: UUID,
    body: ProveedorUpdateRequest,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("proveedores.editar")),
):
    try:
        proveedor = await ActualizarProveedorUseCase(_prov_repo(db)).ejecutar(
            ActualizarProveedorInput(proveedor_id=proveedor_id, **body.model_dump())
        )
    except Exception as e:
        raise _traducir(e)
    return ok(proveedor)


@router.patch("/{proveedor_id}/desactivar", response_model=ApiResponse[ProveedorResponse])
async def desactivar_proveedor(
    proveedor_id: UUID,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("proveedores.editar")),
):
    try:
        proveedor = await DesactivarProveedorUseCase(_prov_repo(db)).ejecutar(proveedor_id)
    except Exception as e:
        raise _traducir(e)
    return ok(proveedor)


@router.patch("/{proveedor_id}/activar", response_model=ApiResponse[ProveedorResponse])
async def activar_proveedor(
    proveedor_id: UUID,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("proveedores.editar")),
):
    try:
        proveedor = await ReactivarProveedorUseCase(_prov_repo(db)).ejecutar(proveedor_id)
    except Exception as e:
        raise _traducir(e)
    return ok(proveedor)


@router.get("/{proveedor_id}/productos", response_model=ApiResponse[list[ProductoProveedorResponse]])
async def listar_productos_de_proveedor(
    proveedor_id: UUID,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(
        require_permission("proveedores.leer", "producto_proveedor.gestionar")
    ),
    incluir_inactivos: bool = Query(default=False),
):
    productos = await ListarProductoProveedorPorProveedorUseCase(_pp_repo(db)).ejecutar(
        proveedor_id, incluir_inactivos,
    )
    return ok(productos)


@router.get("/{proveedor_id}/resumen", response_model=ApiResponse[ResumenProveedorResponse])
async def resumen_proveedor(
    proveedor_id: UUID,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("proveedores.leer")),
):
    resumen = await ResumenProveedorUseCase(
        _recepcion_repo(db), _devolucion_repo(db),
    ).ejecutar(proveedor_id)
    return ok(resumen)


# ========================================================================== #
# FASE 1 — producto_proveedor (colgado de /productos/{producto_id}/proveedores)
# ========================================================================== #
productos_router = APIRouter(route_class=EnvelopeRoute)


@productos_router.post(
    "/{producto_id}/proveedores", response_model=ApiResponse[ProductoProveedorResponse],
    status_code=status.HTTP_201_CREATED,
)
async def vincular_proveedor(
    producto_id: UUID,
    body: ProductoProveedorCreateRequest,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("producto_proveedor.gestionar")),
):
    try:
        pp = await VincularProductoProveedorUseCase(_pp_repo(db)).ejecutar(
            VincularProductoProveedorInput(producto_id=producto_id, **body.model_dump())
        )
    except Exception as e:
        raise _traducir(e)
    return ok(pp)


@productos_router.get(
    "/{producto_id}/proveedores", response_model=ApiResponse[list[ProductoProveedorResponse]],
)
async def listar_proveedores_de_producto(
    producto_id: UUID,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(
        require_permission("proveedores.leer", "producto_proveedor.gestionar")
    ),
    incluir_inactivos: bool = Query(default=False),
):
    productos = await ListarProductoProveedorPorProductoUseCase(_pp_repo(db)).ejecutar(
        producto_id, incluir_inactivos,
    )
    return ok(productos)


@productos_router.delete(
    "/{producto_id}/proveedores/{id_}", response_model=ApiResponse[ProductoProveedorResponse],
)
async def desvincular_proveedor(
    producto_id: UUID,
    id_: UUID,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("producto_proveedor.gestionar")),
):
    try:
        pp = await DesvincularProductoProveedorUseCase(_pp_repo(db)).ejecutar(id_)
    except Exception as e:
        raise _traducir(e)
    return ok(pp)


@productos_router.patch(
    "/{producto_id}/proveedores/{id_}/marcar-principal",
    response_model=ApiResponse[ProductoProveedorResponse],
)
async def marcar_proveedor_principal(
    producto_id: UUID,
    id_: UUID,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("producto_proveedor.gestionar")),
):
    try:
        pp = await MarcarProveedorPrincipalUseCase(_pp_repo(db)).ejecutar(id_)
    except Exception as e:
        raise _traducir(e)
    return ok(pp)


# ========================================================================== #
# FASE 2 — Pedido a proveedor + reorden
# ========================================================================== #
pedidos_router = APIRouter(route_class=EnvelopeRoute)


@pedidos_router.post(
    "", response_model=ApiResponse[PedidoProveedorResponse], status_code=status.HTTP_201_CREATED,
)
async def crear_pedido_proveedor(
    body: PedidoProveedorCreateRequest,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("pedido_proveedor.gestionar")),
):
    sucursal_id = _exige_sucursal(actual)
    try:
        pedido = await CrearPedidoProveedorUseCase(_pedido_repo(db)).ejecutar(
            CrearPedidoProveedorInput(
                proveedor_id=body.proveedor_id, sucursal_id=sucursal_id,
                lineas=[
                    LineaPedidoProveedorInput(
                        producto_id=l.producto_id, cantidad_solicitada=l.cantidad_solicitada,
                        precio_unitario=l.precio_unitario,
                    ) for l in body.lineas
                ],
                fecha_estimada_entrega=body.fecha_estimada_entrega, notas=body.notas,
            )
        )
    except Exception as e:
        raise _traducir(e)
    return ok(pedido)


@pedidos_router.get("", response_model=ApiResponse[list[PedidoProveedorResponse]])
async def listar_pedidos_proveedor(
    request: Request,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("pedido_proveedor.leer")),
    proveedor_id: UUID | None = Query(default=None),
    sucursal_id: UUID | None = Query(default=None),
    estado: EstadoPedidoProveedor | None = Query(default=None),
    paginacion: PageParams = Depends(page_params),
    orden: Sort = Depends(_ORDEN_PEDIDOS),
):
    filtro = FiltroPedidosProveedor(
        proveedor_id=proveedor_id, sucursal_id=_sucursal_efectiva(actual, sucursal_id),
        estado=estado,
    )
    pagina = await ListarPedidosProveedorUseCase(_pedido_repo(db)).ejecutar(filtro, paginacion, orden)
    pagina.items = [PedidoProveedorResponse.model_validate(p) for p in pagina.items]
    return page_response(request, pagina, paginacion, sort=orden, filters=active_filters(filtro))


@pedidos_router.get("/{pedido_id}", response_model=ApiResponse[PedidoProveedorResponse])
async def obtener_pedido_proveedor(
    pedido_id: UUID,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("pedido_proveedor.leer")),
):
    try:
        pedido = await ObtenerPedidoProveedorUseCase(_pedido_repo(db)).ejecutar(pedido_id)
    except Exception as e:
        raise _traducir(e)
    verificar_alcance_sucursal(actual, pedido.sucursal_id)
    return ok(pedido)


@pedidos_router.post(
    "/{pedido_id}/confirmar-envio", response_model=ApiResponse[PedidoProveedorResponse],
)
async def confirmar_envio_pedido(
    pedido_id: UUID,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("pedido_proveedor.confirmar_envio")),
):
    try:
        pedido = await ConfirmarEnvioPedidoProveedorUseCase(_pedido_repo(db)).ejecutar(
            pedido_id, actual.id,
        )
    except Exception as e:
        raise _traducir(e)
    return ok(pedido)


@pedidos_router.post("/{pedido_id}/cancelar", response_model=ApiResponse[PedidoProveedorResponse])
async def cancelar_pedido_proveedor(
    pedido_id: UUID,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("pedido_proveedor.gestionar")),
):
    try:
        pedido = await CancelarPedidoProveedorUseCase(_pedido_repo(db)).ejecutar(pedido_id)
    except Exception as e:
        raise _traducir(e)
    return ok(pedido)


@router.post("/reorden/evaluar", response_model=ApiResponse[list[ReordenGeneradoResponse]])
async def evaluar_reorden(
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("pedido_proveedor.generar_manual")),
    sucursal_id: UUID | None = Query(default=None),
):
    efectiva = _sucursal_efectiva(actual, sucursal_id) or _exige_sucursal(actual)
    resultados = await EvaluarReordenUseCase(
        _pp_repo(db), _pedido_repo(db), SqlAlchemyExistenciaRepository(db),
    ).ejecutar(efectiva, actual.id)
    return ok([
        {"pedido": PedidoProveedorResponse.model_validate(r.pedido), "fue_creado": r.fue_creado}
        for r in resultados
    ])


# ========================================================================== #
# FASE 3 — Recepción de mercancía
# ========================================================================== #
recepciones_router = APIRouter(route_class=EnvelopeRoute)


@recepciones_router.post(
    "", response_model=ApiResponse[RecepcionProveedorResponse], status_code=status.HTTP_201_CREATED,
)
async def registrar_recepcion(
    body: RecepcionProveedorCreateRequest,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("recepcion_proveedor.registrar")),
):
    sucursal_id = _exige_sucursal(actual)
    try:
        recepcion = await RegistrarRecepcionUseCase(
            _recepcion_repo(db), _pedido_repo(db), _aplicar_movimiento_uc(db),
        ).ejecutar(RegistrarRecepcionInput(
            proveedor_id=body.proveedor_id, sucursal_id=sucursal_id, recibido_por=actual.id,
            lineas=[
                LineaRecepcionInput(
                    producto_id=l.producto_id, cantidad_recibida_buena=l.cantidad_recibida_buena,
                    cantidad_defectuosa=l.cantidad_defectuosa, cantidad_esperada=l.cantidad_esperada,
                    motivo_defecto=l.motivo_defecto, accion_defecto=l.accion_defecto,
                    fotos_evidencia_keys=l.fotos_evidencia_keys, notas=l.notas,
                ) for l in body.lineas
            ],
            pedido_id=body.pedido_id, numero_factura=body.numero_factura,
            numero_remision=body.numero_remision, transportista=body.transportista,
            notas=body.notas,
        ))
    except Exception as e:
        raise _traducir(e)
    return ok(recepcion)


@recepciones_router.get("", response_model=ApiResponse[list[RecepcionProveedorResponse]])
async def listar_recepciones(
    request: Request,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("recepcion_proveedor.leer")),
    proveedor_id: UUID | None = Query(default=None),
    sucursal_id: UUID | None = Query(default=None),
    pedido_id: UUID | None = Query(default=None),
    paginacion: PageParams = Depends(page_params),
    orden: Sort = Depends(make_sort_dependency({"fecha_recepcion"}, "fecha_recepcion:desc")),
):
    filtro = FiltroRecepciones(
        proveedor_id=proveedor_id, sucursal_id=_sucursal_efectiva(actual, sucursal_id),
        pedido_id=pedido_id,
    )
    pagina = await ListarRecepcionesUseCase(_recepcion_repo(db)).ejecutar(filtro, paginacion, orden)
    pagina.items = [RecepcionProveedorResponse.model_validate(r) for r in pagina.items]
    return page_response(request, pagina, paginacion, sort=orden, filters=active_filters(filtro))


@recepciones_router.get("/{recepcion_id}", response_model=ApiResponse[RecepcionProveedorResponse])
async def obtener_recepcion(
    recepcion_id: UUID,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("recepcion_proveedor.leer")),
):
    try:
        recepcion = await ObtenerRecepcionUseCase(_recepcion_repo(db)).ejecutar(recepcion_id)
    except Exception as e:
        raise _traducir(e)
    verificar_alcance_sucursal(actual, recepcion.sucursal_id)
    return ok(recepcion)


# ========================================================================== #
# FASE 4 — Devolución a proveedor
# ========================================================================== #
devoluciones_router = APIRouter(route_class=EnvelopeRoute)


@devoluciones_router.post(
    "", response_model=ApiResponse[DevolucionProveedorResponse], status_code=status.HTTP_201_CREATED,
)
async def crear_devolucion(
    body: DevolucionProveedorCreateRequest,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("devolucion_proveedor.gestionar")),
):
    try:
        devolucion = await CrearDevolucionUseCase(_devolucion_repo(db), _recepcion_repo(db)).ejecutar(
            CrearDevolucionInput(
                proveedor_id=body.proveedor_id, recepcion_id=body.recepcion_id,
                creado_por=actual.id,
                lineas=[
                    LineaDevolucionInput(recepcion_detalle_id=l.recepcion_detalle_id, cantidad=l.cantidad)
                    for l in body.lineas
                ],
                notas=body.notas,
            )
        )
    except Exception as e:
        raise _traducir(e)
    return ok(devolucion)


@devoluciones_router.get("", response_model=ApiResponse[list[DevolucionProveedorResponse]])
async def listar_devoluciones(
    request: Request,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("devolucion_proveedor.leer")),
    proveedor_id: UUID | None = Query(default=None),
    estado: EstadoDevolucionProveedor | None = Query(default=None),
    paginacion: PageParams = Depends(page_params),
    orden: Sort = Depends(make_sort_dependency({"created_at"}, "created_at:desc")),
):
    filtro = FiltroDevoluciones(proveedor_id=proveedor_id, estado=estado)
    pagina = await ListarDevolucionesUseCase(_devolucion_repo(db)).ejecutar(filtro, paginacion, orden)
    pagina.items = [DevolucionProveedorResponse.model_validate(d) for d in pagina.items]
    return page_response(request, pagina, paginacion, sort=orden, filters=active_filters(filtro))


@devoluciones_router.get("/{devolucion_id}", response_model=ApiResponse[DevolucionProveedorResponse])
async def obtener_devolucion(
    devolucion_id: UUID,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("devolucion_proveedor.leer")),
):
    try:
        devolucion = await ObtenerDevolucionUseCase(_devolucion_repo(db)).ejecutar(devolucion_id)
    except Exception as e:
        raise _traducir(e)
    return ok(devolucion)


@devoluciones_router.post(
    "/{devolucion_id}/enviar", response_model=ApiResponse[DevolucionProveedorResponse],
)
async def enviar_devolucion(
    devolucion_id: UUID,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("devolucion_proveedor.gestionar")),
):
    try:
        devolucion = await EnviarDevolucionUseCase(_devolucion_repo(db)).ejecutar(devolucion_id)
    except Exception as e:
        raise _traducir(e)
    return ok(devolucion)


@devoluciones_router.post(
    "/{devolucion_id}/cerrar", response_model=ApiResponse[DevolucionProveedorResponse],
)
async def cerrar_devolucion(
    devolucion_id: UUID,
    body: CerrarDevolucionRequest,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("devolucion_proveedor.gestionar")),
):
    try:
        devolucion = await CerrarDevolucionUseCase(_devolucion_repo(db)).ejecutar(
            devolucion_id, body.resultado, body.tipo_resolucion,
        )
    except Exception as e:
        raise _traducir(e)
    return ok(devolucion)
