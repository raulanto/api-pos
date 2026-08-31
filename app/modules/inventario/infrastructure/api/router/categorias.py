from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_permission, UsuarioAutenticado
from app.modules.inventario.application.use_cases.crear_categoria import (
    CrearCategoriaUseCase, CrearCategoriaInput,
)
from app.modules.inventario.application.use_cases.gestionar_categorias import (
    ListarCategoriasUseCase, ObtenerCategoriaUseCase,
    ActualizarCategoriaUseCase, ActualizarCategoriaInput, DesactivarCategoriaUseCase,
)
from app.modules.inventario.infrastructure.api.schemas import (
    CrearCategoriaRequest, ActualizarCategoriaRequest, CategoriaResponse,
)
from .common import cat_repo, traducir, traducir_create

router = APIRouter()

"""
    Endpoint para crear una categoría.

    @param body: Cuerpo de la solicitud.
    @param db: Sesión de la base de datos.
    @param actual: Usuario autenticado.
    @return: Instancia de la clase CategoriaResponse.
"""
@router.post("/categorias", response_model=CategoriaResponse, status_code=status.HTTP_201_CREATED)
async def crear_categoria(
    body: CrearCategoriaRequest,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("inventario.crear")),
):
    try:
        categoria = await CrearCategoriaUseCase(cat_repo(db)).ejecutar(
            CrearCategoriaInput(nombre=body.nombre, categoria_padre_id=body.categoria_padre_id)
        )
    except Exception as e:
        raise traducir_create(e)
    return categoria

"""
    Endpoint para listar categorías.

    @param db: Sesión de la base de datos.
    @param actual: Usuario autenticado.
    @param activo: Indica si la categoría está activa.
    @param categoria_padre_id: ID de la categoría padre.
    @return: Instancia de la clase CategoriaResponse.
"""
@router.get("/categorias", response_model=list[CategoriaResponse])
async def listar_categorias(
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("inventario.leer")),
    activo: bool | None = Query(default=None),
    categoria_padre_id: UUID | None = Query(default=None),
):
    return await ListarCategoriasUseCase(cat_repo(db)).ejecutar(
        activo=activo, categoria_padre_id=categoria_padre_id
    )

"""
    Endpoint para obtener una categoría.

    @param categoria_id: ID de la categoría.
    @param db: Sesión de la base de datos.
    @param actual: Usuario autenticado.
    @return: Instancia de la clase CategoriaResponse.
"""
@router.get("/categorias/{categoria_id}", response_model=CategoriaResponse)
async def obtener_categoria(
    categoria_id: UUID,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("inventario.leer")),
):
    try:
        return await ObtenerCategoriaUseCase(cat_repo(db)).ejecutar(categoria_id)
    except Exception as e:
        raise traducir(e)

"""
    Endpoint para actualizar una categoría.

    @param categoria_id: ID de la categoría.
    @param body: Cuerpo de la solicitud.
    @param db: Sesión de la base de datos.
    @param actual: Usuario autenticado.
    @return: Instancia de la clase CategoriaResponse.
"""
@router.patch("/categorias/{categoria_id}", response_model=CategoriaResponse)
async def actualizar_categoria(
    categoria_id: UUID,
    body: ActualizarCategoriaRequest,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("inventario.editar")),
):
    try:
        categoria = await ActualizarCategoriaUseCase(cat_repo(db)).ejecutar(
            ActualizarCategoriaInput(
                categoria_id=categoria_id,
                nombre=body.nombre,
                categoria_padre_id=body.categoria_padre_id,
                cambiar_padre=body.cambiar_padre,
            )
        )
    except Exception as e:
        raise traducir(e)
    return categoria

"""
    Endpoint para desactivar una categoría.

    @param categoria_id: ID de la categoría.
    @param db: Sesión de la base de datos.
    @param actual: Usuario autenticado.
    @return: Instancia de la clase CategoriaResponse.
"""
@router.patch("/categorias/{categoria_id}/desactivar", response_model=CategoriaResponse)
async def desactivar_categoria(
    categoria_id: UUID,
    db: AsyncSession = Depends(get_db),
    actual: UsuarioAutenticado = Depends(require_permission("inventario.editar")),
):
    try:
        categoria = await DesactivarCategoriaUseCase(cat_repo(db)).ejecutar(categoria_id)
    except Exception as e:
        raise traducir(e)
    return categoria
