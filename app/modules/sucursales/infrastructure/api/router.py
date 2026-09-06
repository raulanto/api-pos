from uuid import UUID

from fastapi import (
    APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_permission, UsuarioAutenticado
from app.shared.responses import (
    ApiResponse, EnvelopeRoute, PageParams, Sort,
    page_params, make_sort_dependency, ok, page_response,
)
from app.shared.filtering import active_filters
from app.modules.sucursales.application.dtos import FiltroSucursales
from app.modules.sucursales.domain.entities import TipoSucursal
from app.modules.sucursales.domain.exceptions import (
    SucursalNoEncontrada, NombreSucursalDuplicado, CodigoSucursalDuplicado,
    SucursalConUsuariosActivos, SucursalPadreNoEncontrada, JerarquiaSucursalInvalida,
)
from app.modules.sucursales.infrastructure.persistence.sucursal_repository_impl import (
    SqlAlchemySucursalRepository,
)
from app.modules.sucursales.infrastructure.api.schemas import (
    CrearSucursalRequest, ActualizarSucursalRequest, SucursalResponse,
)
from app.modules.sucursales.application.use_cases.gestionar_sucursales import (
    ListarSucursalesUseCase, ObtenerSucursalUseCase,
    CrearSucursalUseCase, CrearSucursalInput,
    ActualizarSucursalUseCase, ActualizarSucursalInput,
    DesactivarSucursalUseCase, ReactivarSucursalUseCase,
)
from app.modules.sucursales.application.use_cases.gestionar_fachada import (
    SubirFachadaUseCase, SubirFachadaInput, EliminarFachadaUseCase,
)

router = APIRouter(route_class=EnvelopeRoute)

_ORDEN_SUCURSALES = make_sort_dependency({"nombre", "codigo", "created_at"}, "nombre:asc")
_NOT_FOUND = (SucursalNoEncontrada,)
_CONFLICT = (NombreSucursalDuplicado, CodigoSucursalDuplicado, SucursalConUsuariosActivos)
_BAD_REQUEST = (SucursalPadreNoEncontrada, JerarquiaSucursalInvalida, ValueError)


def _repo(db: AsyncSession) -> SqlAlchemySucursalRepository:
    return SqlAlchemySucursalRepository(db)


def _traducir(e: Exception) -> HTTPException:
    if isinstance(e, _NOT_FOUND):
        return HTTPException(status.HTTP_404_NOT_FOUND, detail=str(e))
    if isinstance(e, _CONFLICT):
        return HTTPException(status.HTTP_409_CONFLICT, detail=str(e))
    if isinstance(e, _BAD_REQUEST):
        return HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e))
    raise e


@router.get("", response_model=ApiResponse[list[SucursalResponse]])
async def listar_sucursales(
    request: Request,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("sucursales.leer")),
    activo: bool | None = Query(default=None),
    q: str | None = Query(default=None, description="Busca en nombre, código, dirección y teléfono"),
    tipo: TipoSucursal | None = Query(default=None),
    sucursal_padre_id: UUID | None = Query(default=None),
    paginacion: PageParams = Depends(page_params),
    orden: Sort = Depends(_ORDEN_SUCURSALES),
):
    filtro = FiltroSucursales(
        activo=activo, busqueda=q, tipo=tipo, sucursal_padre_id=sucursal_padre_id,
    )
    pagina = await ListarSucursalesUseCase(_repo(db)).ejecutar(filtro, paginacion, orden)
    return page_response(
        request, pagina, paginacion, sort=orden, filters=active_filters(filtro),
    )


@router.post(
    "", response_model=ApiResponse[SucursalResponse], status_code=status.HTTP_201_CREATED,
)
async def crear_sucursal(
    body: CrearSucursalRequest,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("sucursales.crear")),
):
    try:
        sucursal = await CrearSucursalUseCase(_repo(db)).ejecutar(CrearSucursalInput(
            nombre=body.nombre, direccion=body.direccion, telefono=body.telefono,
            tipo=body.tipo, codigo=body.codigo, descripcion=body.descripcion,
            colonia=body.colonia, ciudad=body.ciudad, estado=body.estado,
            codigo_postal=body.codigo_postal, pais=body.pais,
            latitud=body.latitud, longitud=body.longitud,
            email=str(body.email) if body.email else None,
            horario_apertura=body.horario_apertura, horario_cierre=body.horario_cierre,
            sucursal_padre_id=body.sucursal_padre_id, permite_ventas=body.permite_ventas,
        ))
    except Exception as e:
        raise _traducir(e)
    return ok(sucursal)


@router.get("/{sucursal_id}", response_model=ApiResponse[SucursalResponse])
async def obtener_sucursal(
    sucursal_id: UUID,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("sucursales.leer")),
):
    try:
        sucursal = await ObtenerSucursalUseCase(_repo(db)).ejecutar(sucursal_id)
    except Exception as e:
        raise _traducir(e)
    return ok(sucursal)


@router.patch("/{sucursal_id}", response_model=ApiResponse[SucursalResponse])
async def actualizar_sucursal(
    sucursal_id: UUID,
    body: ActualizarSucursalRequest,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("sucursales.editar")),
):
    try:
        sucursal = await ActualizarSucursalUseCase(_repo(db)).ejecutar(ActualizarSucursalInput(
            sucursal_id=sucursal_id,
            nombre=body.nombre, direccion=body.direccion, telefono=body.telefono,
            tipo=body.tipo, permite_ventas=body.permite_ventas,
            codigo=body.codigo, cambiar_codigo=body.cambiar_codigo,
            descripcion=body.descripcion, cambiar_descripcion=body.cambiar_descripcion,
            colonia=body.colonia, cambiar_colonia=body.cambiar_colonia,
            ciudad=body.ciudad, cambiar_ciudad=body.cambiar_ciudad,
            estado=body.estado, cambiar_estado=body.cambiar_estado,
            codigo_postal=body.codigo_postal, cambiar_codigo_postal=body.cambiar_codigo_postal,
            pais=body.pais, cambiar_pais=body.cambiar_pais,
            latitud=body.latitud, longitud=body.longitud, cambiar_geo=body.cambiar_geo,
            email=str(body.email) if body.email else None, cambiar_email=body.cambiar_email,
            horario_apertura=body.horario_apertura, horario_cierre=body.horario_cierre,
            cambiar_horario=body.cambiar_horario,
            sucursal_padre_id=body.sucursal_padre_id, cambiar_padre=body.cambiar_padre,
        ))
    except Exception as e:
        raise _traducir(e)
    return ok(sucursal)


@router.patch("/{sucursal_id}/desactivar", response_model=ApiResponse[SucursalResponse])
async def desactivar_sucursal(
    sucursal_id: UUID,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("sucursales.desactivar")),
):
    try:
        sucursal = await DesactivarSucursalUseCase(_repo(db)).ejecutar(sucursal_id)
    except Exception as e:
        raise _traducir(e)
    return ok(sucursal)


@router.patch("/{sucursal_id}/reactivar", response_model=ApiResponse[SucursalResponse])
async def reactivar_sucursal(
    sucursal_id: UUID,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("sucursales.desactivar")),
):
    try:
        sucursal = await ReactivarSucursalUseCase(_repo(db)).ejecutar(sucursal_id)
    except Exception as e:
        raise _traducir(e)
    return ok(sucursal)


# --------------------------------------------------------------------------- #
# Imagen de fachada (S3)
# --------------------------------------------------------------------------- #
@router.post("/{sucursal_id}/fachada", response_model=ApiResponse[SucursalResponse])
async def subir_fachada(
    sucursal_id: UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("sucursales.editar")),
):
    contenido = await file.read()
    try:
        sucursal = await SubirFachadaUseCase(_repo(db)).ejecutar(SubirFachadaInput(
            sucursal_id=sucursal_id,
            contenido=contenido,
            content_type=file.content_type or "",
        ))
    except Exception as e:
        raise _traducir(e)
    return ok(sucursal)


@router.delete(
    "/{sucursal_id}/fachada", response_model=ApiResponse[SucursalResponse],
)
async def eliminar_fachada(
    sucursal_id: UUID,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("sucursales.editar")),
):
    try:
        sucursal = await EliminarFachadaUseCase(_repo(db)).ejecutar(sucursal_id)
    except Exception as e:
        raise _traducir(e)
    return ok(sucursal)
