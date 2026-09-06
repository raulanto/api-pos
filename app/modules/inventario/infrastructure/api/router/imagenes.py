from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_permission, UsuarioAutenticado
from app.shared.responses import ApiResponse, EnvelopeRoute, ok
from app.modules.inventario.domain.exceptions import UnidadNoEncontrada
from app.modules.inventario.application.use_cases.gestionar_imagenes import (
    ListarImagenesProductoUseCase, ListarImagenesUnidadUseCase,
    AgregarImagenUseCase, AgregarImagenInput,
    ActualizarImagenUseCase, ActualizarImagenInput,
    EliminarImagenUseCase,
)
from app.modules.inventario.application.use_cases.subir_imagen import (
    SubirImagenUseCase, SubirImagenInput,
)
from app.modules.inventario.infrastructure.api.schemas import (
    AgregarImagenRequest, ActualizarImagenRequest, ImagenResponse,
)
from .common import almacen_imagenes, imagen_repo, prod_repo, unidad_repo, traducir

router = APIRouter(route_class=EnvelopeRoute)

# Las entidades `ProductoImagen` ya traen `url` / `thumbnail_url` resueltas
# (el mapper las prefirma al leer una imagen S3), así que se serializan directo
# con `ImagenResponse.model_config = from_attributes`.


async def _unidad_del_producto(db: AsyncSession, producto_id: UUID, unidad_id: UUID) -> None:
    """404 si `unidad_id` no existe o no pertenece a `producto_id` (misma
    verificación que hace el router de unidades para PATCH/DELETE)."""
    unidad = await unidad_repo(db).obtener(unidad_id)
    if unidad is None or unidad.producto_id != producto_id:
        raise traducir(UnidadNoEncontrada(
            f"El producto {producto_id} no tiene la presentación {unidad_id}."
        ))


# --------------------------------------------------------------------------- #
# Galería de un producto (simple o kit)
# --------------------------------------------------------------------------- #
@router.get(
    "/productos/{producto_id}/imagenes", response_model=ApiResponse[list[ImagenResponse]],
)
async def listar_imagenes_producto(
    producto_id: UUID,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("inventario.leer")),
):
    try:
        imagenes = await ListarImagenesProductoUseCase(
            imagen_repo(db), prod_repo(db)
        ).ejecutar(producto_id)
    except Exception as e:
        raise traducir(e)
    return ok(imagenes)


@router.post(
    "/productos/{producto_id}/imagenes", response_model=ApiResponse[ImagenResponse],
    status_code=status.HTTP_201_CREATED,
)
async def agregar_imagen_producto(
    producto_id: UUID,
    body: AgregarImagenRequest,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("inventario.editar")),
):
    try:
        imagen = await AgregarImagenUseCase(
            imagen_repo(db), prod_repo(db), unidad_repo(db)
        ).ejecutar(AgregarImagenInput(
            url=str(body.url), producto_id=producto_id,
            alt_texto=body.alt_texto, orden=body.orden, es_principal=body.es_principal,
        ))
    except Exception as e:
        raise traducir(e)
    return ok(imagen)


@router.post(
    "/productos/{producto_id}/imagenes/upload", response_model=ApiResponse[ImagenResponse],
    status_code=status.HTTP_201_CREATED,
)
async def subir_imagen_producto(
    producto_id: UUID,
    file: UploadFile = File(...),
    alt_texto: str | None = Form(default=None),
    orden: int = Form(default=0, ge=0),
    es_principal: bool = Form(default=False),
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("inventario.editar")),
):
    contenido = await file.read()
    try:
        imagen = await SubirImagenUseCase(
            imagen_repo(db), prod_repo(db), unidad_repo(db), almacen_imagenes()
        ).ejecutar(SubirImagenInput(
            contenido=contenido, content_type=file.content_type or "",
            producto_id=producto_id,
            alt_texto=alt_texto, orden=orden, es_principal=es_principal,
        ))
    except Exception as e:
        raise traducir(e)
    return ok(imagen)


@router.patch(
    "/productos/{producto_id}/imagenes/{imagen_id}", response_model=ApiResponse[ImagenResponse],
)
async def actualizar_imagen_producto(
    producto_id: UUID,
    imagen_id: UUID,
    body: ActualizarImagenRequest,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("inventario.editar")),
):
    try:
        imagen = await ActualizarImagenUseCase(imagen_repo(db)).ejecutar(ActualizarImagenInput(
            imagen_id=imagen_id, producto_id=producto_id,
            url=str(body.url) if body.url is not None else None,
            alt_texto=body.alt_texto, cambiar_alt_texto=body.cambiar_alt_texto,
            orden=body.orden, es_principal=body.es_principal,
        ))
    except Exception as e:
        raise traducir(e)
    return ok(imagen)


@router.delete(
    "/productos/{producto_id}/imagenes/{imagen_id}", status_code=status.HTTP_204_NO_CONTENT,
)
async def eliminar_imagen_producto(
    producto_id: UUID,
    imagen_id: UUID,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("inventario.editar")),
):
    try:
        await EliminarImagenUseCase(imagen_repo(db), almacen_imagenes()).ejecutar(
            imagen_id, producto_id=producto_id,
        )
    except Exception as e:
        raise traducir(e)


# --------------------------------------------------------------------------- #
# Galería de una presentación de venta (producto_unidad) — p. ej. la unidad
# suelta de un producto fraccionable.
# --------------------------------------------------------------------------- #
@router.get(
    "/productos/{producto_id}/unidades/{unidad_id}/imagenes",
    response_model=ApiResponse[list[ImagenResponse]],
)
async def listar_imagenes_unidad(
    producto_id: UUID,
    unidad_id: UUID,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("inventario.leer")),
):
    try:
        await _unidad_del_producto(db, producto_id, unidad_id)
        imagenes = await ListarImagenesUnidadUseCase(
            imagen_repo(db), unidad_repo(db)
        ).ejecutar(unidad_id)
    except Exception as e:
        raise traducir(e)
    return ok(imagenes)


@router.post(
    "/productos/{producto_id}/unidades/{unidad_id}/imagenes",
    response_model=ApiResponse[ImagenResponse], status_code=status.HTTP_201_CREATED,
)
async def agregar_imagen_unidad(
    producto_id: UUID,
    unidad_id: UUID,
    body: AgregarImagenRequest,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("inventario.editar")),
):
    try:
        await _unidad_del_producto(db, producto_id, unidad_id)
        imagen = await AgregarImagenUseCase(
            imagen_repo(db), prod_repo(db), unidad_repo(db)
        ).ejecutar(AgregarImagenInput(
            url=str(body.url), producto_unidad_id=unidad_id,
            alt_texto=body.alt_texto, orden=body.orden, es_principal=body.es_principal,
        ))
    except Exception as e:
        raise traducir(e)
    return ok(imagen)


@router.post(
    "/productos/{producto_id}/unidades/{unidad_id}/imagenes/upload",
    response_model=ApiResponse[ImagenResponse], status_code=status.HTTP_201_CREATED,
)
async def subir_imagen_unidad(
    producto_id: UUID,
    unidad_id: UUID,
    file: UploadFile = File(...),
    alt_texto: str | None = Form(default=None),
    orden: int = Form(default=0, ge=0),
    es_principal: bool = Form(default=False),
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("inventario.editar")),
):
    await _unidad_del_producto(db, producto_id, unidad_id)
    contenido = await file.read()
    try:
        imagen = await SubirImagenUseCase(
            imagen_repo(db), prod_repo(db), unidad_repo(db), almacen_imagenes()
        ).ejecutar(SubirImagenInput(
            contenido=contenido, content_type=file.content_type or "",
            producto_unidad_id=unidad_id,
            alt_texto=alt_texto, orden=orden, es_principal=es_principal,
        ))
    except Exception as e:
        raise traducir(e)
    return ok(imagen)


@router.patch(
    "/productos/{producto_id}/unidades/{unidad_id}/imagenes/{imagen_id}",
    response_model=ApiResponse[ImagenResponse],
)
async def actualizar_imagen_unidad(
    producto_id: UUID,
    unidad_id: UUID,
    imagen_id: UUID,
    body: ActualizarImagenRequest,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("inventario.editar")),
):
    try:
        await _unidad_del_producto(db, producto_id, unidad_id)
        imagen = await ActualizarImagenUseCase(imagen_repo(db)).ejecutar(ActualizarImagenInput(
            imagen_id=imagen_id, producto_unidad_id=unidad_id,
            url=str(body.url) if body.url is not None else None,
            alt_texto=body.alt_texto, cambiar_alt_texto=body.cambiar_alt_texto,
            orden=body.orden, es_principal=body.es_principal,
        ))
    except Exception as e:
        raise traducir(e)
    return ok(imagen)


@router.delete(
    "/productos/{producto_id}/unidades/{unidad_id}/imagenes/{imagen_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def eliminar_imagen_unidad(
    producto_id: UUID,
    unidad_id: UUID,
    imagen_id: UUID,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("inventario.editar")),
):
    try:
        await _unidad_del_producto(db, producto_id, unidad_id)
        await EliminarImagenUseCase(imagen_repo(db), almacen_imagenes()).ejecutar(
            imagen_id, producto_unidad_id=unidad_id,
        )
    except Exception as e:
        raise traducir(e)
