from datetime import date, datetime
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

from app.modules.agenda.domain import exceptions as aexc
from app.modules.agenda.domain.value_objects import EstadoCita
from app.modules.agenda.application.dtos import FiltroCitas
from app.modules.agenda.application.use_cases.gestionar_catalogo import (
    CrearRecursoUseCase, CrearRecursoInput, ListarRecursosUseCase,
    RenombrarRecursoUseCase, DesactivarRecursoUseCase, ReactivarRecursoUseCase,
    CalificarEmpleadoUseCase, DescalificarEmpleadoUseCase, ListarServiciosDeEmpleadoUseCase,
    CrearHorarioUseCase, EliminarHorarioUseCase,
    CrearExcepcionUseCase, EliminarExcepcionUseCase, CrearHorarioRecursoUseCase,
)
from app.modules.agenda.application.use_cases.crear_cita import CrearCitaUseCase, CrearCitaInput
from app.modules.agenda.application.use_cases.responder_oferta import (
    AceptarOfertaUseCase, RechazarOfertaUseCase, ResponderOfertaInput,
)
from app.modules.agenda.application.use_cases.gestionar_cita import (
    AsignarManualUseCase, AsignarManualInput, OfertarDeNuevoUseCase,
    IniciarCitaUseCase, CompletarCitaUseCase, CancelarCitaUseCase, MarcarNoShowUseCase,
    ObtenerCitaUseCase, ListarCitasUseCase,
)
from app.modules.agenda.application.use_cases.facturar_cita import (
    FacturarCitaUseCase, FacturarCitaInput,
)
from app.modules.agenda.infrastructure.persistence.repositories_impl import (
    SqlAlchemyRecursoRepository, SqlAlchemyDisponibilidadRepository, SqlAlchemyCitaRepository,
)
from app.modules.inventario.infrastructure.persistence.repositories.producto import (
    SqlAlchemyProductoRepository,
)
from app.modules.ventas.infrastructure.api.router import (
    _venta_use_case as _crear_venta_uc, _traducir as _traducir_venta,
)
from app.modules.ventas.application.use_cases.crear_venta import PagoInput
from app.modules.ventas.infrastructure.api.schemas import VentaResponse
from app.modules.agenda.infrastructure.api.schemas import (
    RecursoCreateRequest, RecursoRenameRequest, RecursoResponse,
    EmpleadoServicioResponse,
    HorarioBaseRequest, HorarioBaseResponse, ExcepcionRequest, ExcepcionResponse,
    HorarioRecursoRequest, HorarioRecursoResponse,
    CrearCitaRequest, AsignarManualRequest, CancelarCitaRequest, FacturarCitaRequest,
    CitaResponse,
)

router = APIRouter(route_class=EnvelopeRoute)

_ORDEN_CITAS = make_sort_dependency({"fecha_hora_inicio", "created_at"}, "fecha_hora_inicio:desc")
_INC_CITAS = make_include_dependency({"cliente", "empleado"})


# --------------------------------------------------------------------------- #
# Excepciones de dominio -> HTTP
# --------------------------------------------------------------------------- #
_NOT_FOUND = (
    aexc.RecursoNoEncontrado, aexc.EmpleadoServicioNoEncontrado, aexc.CitaNoEncontrada,
)
_CONFLICT = (
    aexc.NombreRecursoEnUso, aexc.RecursoNoDisponible, aexc.EmpleadoYaAsignado,
    aexc.CitaYaFacturada,
)
_FORBIDDEN = (
    aexc.AsignacionNoPropia,
)
_BAD_REQUEST = (
    aexc.ServicioNoAgendable, aexc.SucursalCruzadaNoPermitida, aexc.EmpleadoNoCalificado,
    aexc.CitaNoOfertable, aexc.OfertaNoVigente, aexc.TransicionCitaInvalida,
    aexc.CitaNoFacturable, ValueError,
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
    # Facturar una cita reusa `CrearVentaUseCase`: sus errores (stock, caja,
    # crédito, cupón, sucursal no operativa, ...) los mapea el traductor de ventas.
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


def _recurso_repo(db: AsyncSession) -> SqlAlchemyRecursoRepository:
    return SqlAlchemyRecursoRepository(db)


def _disp_repo(db: AsyncSession) -> SqlAlchemyDisponibilidadRepository:
    return SqlAlchemyDisponibilidadRepository(db)


def _cita_repo(db: AsyncSession) -> SqlAlchemyCitaRepository:
    return SqlAlchemyCitaRepository(db)


# ========================================================================== #
# CATÁLOGO: recursos
# ========================================================================== #
@router.post(
    "/recursos", response_model=ApiResponse[RecursoResponse], status_code=status.HTTP_201_CREATED,
)
async def crear_recurso(
    body: RecursoCreateRequest,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("agenda.administrar")),
):
    sucursal_id = _exige_sucursal(actual)
    try:
        recurso = await CrearRecursoUseCase(_recurso_repo(db)).ejecutar(
            CrearRecursoInput(sucursal_id=sucursal_id, nombre=body.nombre, tipo=body.tipo)
        )
    except Exception as e:
        raise _traducir(e)
    return ok(recurso)


@router.get("/recursos", response_model=ApiResponse[list[RecursoResponse]])
async def listar_recursos(
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(
        require_permission("agenda.administrar", "citas.gestionar")
    ),
    sucursal_id: UUID | None = Query(default=None),
    incluir_inactivos: bool = Query(default=False),
):
    efectiva = _sucursal_efectiva(actual, sucursal_id) or _exige_sucursal(actual)
    recursos = await ListarRecursosUseCase(_recurso_repo(db)).ejecutar(efectiva, incluir_inactivos)
    return ok(recursos)


@router.patch("/recursos/{recurso_id}", response_model=ApiResponse[RecursoResponse])
async def renombrar_recurso(
    recurso_id: UUID,
    body: RecursoRenameRequest,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("agenda.administrar")),
):
    try:
        recurso = await RenombrarRecursoUseCase(_recurso_repo(db)).ejecutar(recurso_id, body.nombre)
        verificar_alcance_sucursal(actual, recurso.sucursal_id)
    except HTTPException:
        raise
    except Exception as e:
        raise _traducir(e)
    return ok(recurso)


@router.delete("/recursos/{recurso_id}", response_model=ApiResponse[RecursoResponse])
async def desactivar_recurso(
    recurso_id: UUID,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("agenda.administrar")),
):
    try:
        recurso = await DesactivarRecursoUseCase(_recurso_repo(db)).ejecutar(recurso_id)
        verificar_alcance_sucursal(actual, recurso.sucursal_id)
    except HTTPException:
        raise
    except Exception as e:
        raise _traducir(e)
    return ok(recurso)


@router.patch("/recursos/{recurso_id}/reactivar", response_model=ApiResponse[RecursoResponse])
async def reactivar_recurso(
    recurso_id: UUID,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("agenda.administrar")),
):
    try:
        recurso = await ReactivarRecursoUseCase(_recurso_repo(db)).ejecutar(recurso_id)
        verificar_alcance_sucursal(actual, recurso.sucursal_id)
    except HTTPException:
        raise
    except Exception as e:
        raise _traducir(e)
    return ok(recurso)


@router.post(
    "/recursos/{recurso_id}/horarios", response_model=ApiResponse[HorarioRecursoResponse],
    status_code=status.HTTP_201_CREATED,
)
async def crear_horario_recurso(
    recurso_id: UUID,
    body: HorarioRecursoRequest,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("agenda.administrar")),
):
    try:
        horario = await CrearHorarioRecursoUseCase(_disp_repo(db)).ejecutar(
            recurso_id, body.dia_semana, body.hora_inicio, body.hora_fin,
        )
    except Exception as e:
        raise _traducir(e)
    return ok(horario)


@router.get(
    "/recursos/{recurso_id}/horarios", response_model=ApiResponse[list[HorarioRecursoResponse]],
)
async def listar_horarios_recurso(
    recurso_id: UUID,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(
        require_permission("agenda.administrar", "citas.gestionar")
    ),
):
    horarios = await _disp_repo(db).horarios_del_recurso(recurso_id)
    return ok(horarios)


# ========================================================================== #
# CATÁLOGO: empleados (servicios que atiende, horario, excepciones)
# ========================================================================== #
@router.post(
    "/empleados/{empleado_id}/servicios", response_model=ApiResponse[EmpleadoServicioResponse],
    status_code=status.HTTP_201_CREATED,
)
async def calificar_empleado(
    empleado_id: UUID,
    servicio_id: UUID = Query(...),
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("agenda.administrar")),
):
    es = await CalificarEmpleadoUseCase(_disp_repo(db)).ejecutar(empleado_id, servicio_id)
    return ok(es)


@router.delete("/empleados/{empleado_id}/servicios/{servicio_id}", response_model=ApiResponse[None])
async def descalificar_empleado(
    empleado_id: UUID,
    servicio_id: UUID,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("agenda.administrar")),
):
    await DescalificarEmpleadoUseCase(_disp_repo(db)).ejecutar(empleado_id, servicio_id)
    return ok(None)


@router.get(
    "/empleados/{empleado_id}/servicios", response_model=ApiResponse[list[EmpleadoServicioResponse]],
)
async def listar_servicios_de_empleado(
    empleado_id: UUID,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(
        require_permission("agenda.administrar", "citas.gestionar")
    ),
):
    servicios = await ListarServiciosDeEmpleadoUseCase(_disp_repo(db)).ejecutar(empleado_id)
    return ok(servicios)


@router.post(
    "/empleados/{empleado_id}/horarios", response_model=ApiResponse[HorarioBaseResponse],
    status_code=status.HTTP_201_CREATED,
)
async def crear_horario_empleado(
    empleado_id: UUID,
    body: HorarioBaseRequest,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("agenda.administrar")),
):
    try:
        horario = await CrearHorarioUseCase(_disp_repo(db)).ejecutar(
            empleado_id, body.sucursal_id, body.dia_semana, body.hora_inicio, body.hora_fin,
        )
    except Exception as e:
        raise _traducir(e)
    return ok(horario)


@router.get(
    "/empleados/{empleado_id}/horarios", response_model=ApiResponse[list[HorarioBaseResponse]],
)
async def listar_horarios_empleado(
    empleado_id: UUID,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(
        require_permission("agenda.administrar", "citas.gestionar", "citas.ver_propias")
    ),
):
    if empleado_id != actual.id and not actual.tiene_permiso(
        "agenda.administrar", "citas.gestionar",
    ):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Sólo podés ver tu propio horario")
    horarios = (await _disp_repo(db).horarios_de([empleado_id], None)).get(empleado_id, [])
    return ok(horarios)


@router.delete("/empleados/{empleado_id}/horarios/{horario_id}", response_model=ApiResponse[None])
async def eliminar_horario_empleado(
    empleado_id: UUID,
    horario_id: UUID,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("agenda.administrar")),
):
    await EliminarHorarioUseCase(_disp_repo(db)).ejecutar(horario_id)
    return ok(None)


@router.post(
    "/empleados/{empleado_id}/excepciones", response_model=ApiResponse[ExcepcionResponse],
    status_code=status.HTTP_201_CREATED,
)
async def crear_excepcion(
    empleado_id: UUID,
    body: ExcepcionRequest,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("agenda.administrar")),
):
    try:
        excepcion = await CrearExcepcionUseCase(_disp_repo(db)).ejecutar(
            empleado_id, body.fecha, body.tipo, body.hora_inicio, body.hora_fin, body.motivo,
        )
    except Exception as e:
        raise _traducir(e)
    return ok(excepcion)


@router.get(
    "/empleados/{empleado_id}/excepciones", response_model=ApiResponse[list[ExcepcionResponse]],
)
async def listar_excepciones(
    empleado_id: UUID,
    fecha: date = Query(...),
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(
        require_permission("agenda.administrar", "citas.gestionar", "citas.ver_propias")
    ),
):
    if empleado_id != actual.id and not actual.tiene_permiso(
        "agenda.administrar", "citas.gestionar",
    ):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Sólo podés ver tus propias excepciones")
    excepciones = (await _disp_repo(db).excepciones_de([empleado_id], fecha)).get(empleado_id, [])
    return ok(excepciones)


@router.delete(
    "/empleados/{empleado_id}/excepciones/{excepcion_id}", response_model=ApiResponse[None],
)
async def eliminar_excepcion(
    empleado_id: UUID,
    excepcion_id: UUID,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("agenda.administrar")),
):
    await EliminarExcepcionUseCase(_disp_repo(db)).ejecutar(excepcion_id)
    return ok(None)


# ========================================================================== #
# CITAS
# ========================================================================== #
@router.post(
    "/citas", response_model=ApiResponse[CitaResponse], status_code=status.HTTP_201_CREATED,
)
async def crear_cita(
    body: CrearCitaRequest,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("citas.gestionar")),
):
    sucursal_id = _exige_sucursal(actual)
    try:
        cita = await CrearCitaUseCase(
            _cita_repo(db), SqlAlchemyProductoRepository(db), _recurso_repo(db), _disp_repo(db),
        ).ejecutar(CrearCitaInput(
            servicio_id=body.servicio_id, sucursal_id=sucursal_id,
            fecha_hora_inicio=body.fecha_hora_inicio, creado_por_usuario_id=actual.id,
            cliente_id=body.cliente_id, recurso_id=body.recurso_id,
            disponibilidad_cruzada=body.disponibilidad_cruzada,
            politica_cancelacion_horas=body.politica_cancelacion_horas,
            penalizacion_cancelacion=body.penalizacion_cancelacion,
        ))
    except Exception as e:
        raise _traducir(e)
    return ok(cita)


@router.get("/citas", response_model=ApiResponse[list[CitaResponse]])
async def listar_citas(
    request: Request,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(
        require_permission("citas.gestionar", "citas.ver_propias")
    ),
    sucursal_id: UUID | None = Query(default=None),
    servicio_id: UUID | None = Query(default=None),
    empleado_id: UUID | None = Query(default=None),
    cliente_id: UUID | None = Query(default=None),
    estado: EstadoCita | None = Query(default=None),
    desde: datetime | None = Query(default=None),
    hasta: datetime | None = Query(default=None),
    paginacion: PageParams = Depends(page_params),
    orden: Sort = Depends(_ORDEN_CITAS),
    include: frozenset[str] = Depends(_INC_CITAS),
):
    efectivo_empleado = empleado_id
    if not actual.tiene_permiso("citas.gestionar"):
        if empleado_id is not None and empleado_id != actual.id:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, detail="Sólo podés ver tus propias citas"
            )
        efectivo_empleado = actual.id
    filtro = FiltroCitas(
        sucursal_id=_sucursal_efectiva(actual, sucursal_id), servicio_id=servicio_id,
        empleado_id=efectivo_empleado, cliente_id=cliente_id, estado=estado,
        desde=desde, hasta=hasta,
    )
    pagina = await ListarCitasUseCase(_cita_repo(db)).ejecutar(filtro, paginacion, orden, include)
    pagina.items = [CitaResponse.model_validate(c) for c in pagina.items]
    return page_response(
        request, pagina, paginacion, sort=orden, filters=active_filters(filtro),
    )


@router.get("/citas/{cita_id}", response_model=ApiResponse[CitaResponse])
async def obtener_cita(
    cita_id: UUID,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(
        require_permission("citas.gestionar", "citas.ver_propias")
    ),
):
    try:
        cita = await ObtenerCitaUseCase(_cita_repo(db)).ejecutar(cita_id)
    except Exception as e:
        raise _traducir(e)
    if not actual.tiene_permiso("citas.gestionar") and cita.empleado_id != actual.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Sólo podés ver tus propias citas")
    verificar_alcance_sucursal(actual, cita.sucursal_id)
    return ok(cita)


@router.post("/citas/{cita_id}/ofertar", response_model=ApiResponse[CitaResponse])
async def ofertar_de_nuevo(
    cita_id: UUID,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("citas.gestionar")),
):
    try:
        cita = await OfertarDeNuevoUseCase(_cita_repo(db), _disp_repo(db)).ejecutar(cita_id)
    except Exception as e:
        raise _traducir(e)
    return ok(cita)


@router.post("/citas/{cita_id}/asignar-manual", response_model=ApiResponse[CitaResponse])
async def asignar_manual(
    cita_id: UUID,
    body: AsignarManualRequest,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("citas.gestionar")),
):
    try:
        cita = await AsignarManualUseCase(_cita_repo(db), _disp_repo(db)).ejecutar(
            AsignarManualInput(cita_id=cita_id, empleado_id=body.empleado_id)
        )
    except Exception as e:
        raise _traducir(e)
    return ok(cita)


@router.post("/citas/{cita_id}/aceptar", response_model=ApiResponse[CitaResponse])
async def aceptar_oferta(
    cita_id: UUID,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("citas.responder_oferta")),
):
    try:
        cita = await AceptarOfertaUseCase(_cita_repo(db), _disp_repo(db)).ejecutar(
            ResponderOfertaInput(cita_id=cita_id, empleado_id=actual.id)
        )
    except Exception as e:
        raise _traducir(e)
    return ok(cita)


@router.post("/citas/{cita_id}/rechazar", response_model=ApiResponse[CitaResponse])
async def rechazar_oferta(
    cita_id: UUID,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("citas.responder_oferta")),
):
    try:
        cita = await RechazarOfertaUseCase(_cita_repo(db)).ejecutar(
            ResponderOfertaInput(cita_id=cita_id, empleado_id=actual.id)
        )
    except Exception as e:
        raise _traducir(e)
    return ok(cita)


def _exige_dueno_o_gestor(actual: UsuarioAutenticado, cita) -> None:
    if not actual.tiene_permiso("citas.gestionar") and cita.empleado_id != actual.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="No es tu cita")


@router.post("/citas/{cita_id}/iniciar", response_model=ApiResponse[CitaResponse])
async def iniciar_cita(
    cita_id: UUID,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(
        require_permission("citas.gestionar", "citas.responder_oferta")
    ),
):
    try:
        existente = await ObtenerCitaUseCase(_cita_repo(db)).ejecutar(cita_id)
        _exige_dueno_o_gestor(actual, existente)
        cita = await IniciarCitaUseCase(_cita_repo(db)).ejecutar(cita_id)
    except HTTPException:
        raise
    except Exception as e:
        raise _traducir(e)
    return ok(cita)


@router.post("/citas/{cita_id}/completar", response_model=ApiResponse[CitaResponse])
async def completar_cita(
    cita_id: UUID,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(
        require_permission("citas.gestionar", "citas.responder_oferta")
    ),
):
    try:
        existente = await ObtenerCitaUseCase(_cita_repo(db)).ejecutar(cita_id)
        _exige_dueno_o_gestor(actual, existente)
        cita = await CompletarCitaUseCase(_cita_repo(db)).ejecutar(cita_id)
    except HTTPException:
        raise
    except Exception as e:
        raise _traducir(e)
    return ok(cita)


@router.patch("/citas/{cita_id}/cancelar", response_model=ApiResponse[CitaResponse])
async def cancelar_cita(
    cita_id: UUID,
    body: CancelarCitaRequest,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("citas.gestionar")),
):
    try:
        cita = await CancelarCitaUseCase(_cita_repo(db)).ejecutar(cita_id, body.motivo)
    except Exception as e:
        raise _traducir(e)
    return ok(cita)


@router.patch("/citas/{cita_id}/no-show", response_model=ApiResponse[CitaResponse])
async def marcar_no_show(
    cita_id: UUID,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("citas.gestionar")),
):
    try:
        cita = await MarcarNoShowUseCase(_cita_repo(db)).ejecutar(cita_id)
    except Exception as e:
        raise _traducir(e)
    return ok(cita)


@router.post(
    "/citas/{cita_id}/facturar", response_model=ApiResponse[VentaResponse],
    status_code=status.HTTP_201_CREATED,
)
async def facturar_cita(
    cita_id: UUID,
    body: FacturarCitaRequest,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("citas.gestionar")),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    """Cobra una cita `completada`: arma una venta de 1 línea (el servicio, al
    precio vigente) reusando `CrearVentaUseCase` — mismo patrón que
    `POST /pedidos/{id}/facturar`."""
    uc = FacturarCitaUseCase(_cita_repo(db), SqlAlchemyProductoRepository(db), _crear_venta_uc(db))
    try:
        venta = await uc.ejecutar(FacturarCitaInput(
            cita_id=cita_id, usuario_id=actual.id, caja_turno_id=body.caja_turno_id,
            pagos=[
                PagoInput(monto=p.monto, metodo_pago=p.metodo_pago, monto_recibido=p.monto_recibido)
                for p in body.pagos
            ],
            idempotency_key=idempotency_key,
        ))
    except HTTPException:
        raise
    except Exception as e:
        raise _traducir(e)
    verificar_alcance_sucursal(actual, venta.sucursal_id)
    return ok(venta)
