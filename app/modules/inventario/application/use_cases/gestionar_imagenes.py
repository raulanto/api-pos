"""Casos de uso de la galería de imágenes (`producto_imagen`).

El dueño de una imagen es EXACTAMENTE uno: un producto (simple o kit) o una
presentación de venta (`producto_unidad`, p. ej. la unidad suelta de un
fraccionable). Reglas:
- El dueño debe existir.
- `es_principal=True` desmarca cualquier otra imagen principal del mismo dueño
  (sólo puede haber una portada por dueño).
- La baja es física: una imagen no tiene referencias históricas que preservar.
"""
from dataclasses import dataclass
from uuid import UUID

from app.modules.inventario.domain.entities import ProductoImagen
from app.modules.inventario.domain.exceptions import (
    ProductoNoEncontrado, UnidadNoEncontrada, ImagenNoEncontrada, ImagenInvalida,
)
from app.modules.inventario.application.ports.producto_repository import ProductoRepository
from app.modules.inventario.application.ports.unidad_repository import (
    ProductoUnidadRepository,
)
from app.modules.inventario.application.ports.imagen_repository import ImagenRepository
from app.modules.inventario.application.ports.almacen_imagenes import AlmacenImagenes


async def _validar_dueno(
    producto_repo: ProductoRepository,
    unidad_repo: ProductoUnidadRepository,
    producto_id: UUID | None,
    producto_unidad_id: UUID | None,
) -> None:
    if (producto_id is None) == (producto_unidad_id is None):
        raise ImagenInvalida(
            "Una imagen pertenece a exactamente un producto O una presentación."
        )
    if producto_id is not None:
        if await producto_repo.obtener_por_id(producto_id) is None:
            raise ProductoNoEncontrado(f"No existe el producto {producto_id}")
    else:
        if await unidad_repo.obtener(producto_unidad_id) is None:
            raise UnidadNoEncontrada(f"No existe la presentación {producto_unidad_id}")


# --------------------------------------------------------------------------- #
class ListarImagenesProductoUseCase:
    def __init__(self, imagen_repo: ImagenRepository, producto_repo: ProductoRepository):
        self._repo = imagen_repo
        self._producto_repo = producto_repo

    async def ejecutar(self, producto_id: UUID) -> list[ProductoImagen]:
        if await self._producto_repo.obtener_por_id(producto_id) is None:
            raise ProductoNoEncontrado(f"No existe el producto {producto_id}")
        return await self._repo.listar_por_producto(producto_id)


class ListarImagenesUnidadUseCase:
    def __init__(self, imagen_repo: ImagenRepository, unidad_repo: ProductoUnidadRepository):
        self._repo = imagen_repo
        self._unidad_repo = unidad_repo

    async def ejecutar(self, producto_unidad_id: UUID) -> list[ProductoImagen]:
        if await self._unidad_repo.obtener(producto_unidad_id) is None:
            raise UnidadNoEncontrada(f"No existe la presentación {producto_unidad_id}")
        return await self._repo.listar_por_unidad(producto_unidad_id)


# --------------------------------------------------------------------------- #
@dataclass
class AgregarImagenInput:
    url: str
    producto_id: UUID | None = None
    producto_unidad_id: UUID | None = None
    alt_texto: str | None = None
    orden: int = 0
    es_principal: bool = False


class AgregarImagenUseCase:
    def __init__(
        self,
        imagen_repo: ImagenRepository,
        producto_repo: ProductoRepository,
        unidad_repo: ProductoUnidadRepository,
    ):
        self._repo = imagen_repo
        self._producto_repo = producto_repo
        self._unidad_repo = unidad_repo

    async def ejecutar(self, data: AgregarImagenInput) -> ProductoImagen:
        await _validar_dueno(
            self._producto_repo, self._unidad_repo, data.producto_id, data.producto_unidad_id
        )
        imagen = ProductoImagen.crear(
            url=data.url,
            producto_id=data.producto_id,
            producto_unidad_id=data.producto_unidad_id,
            alt_texto=data.alt_texto,
            orden=data.orden,
            es_principal=data.es_principal,
        )
        if data.es_principal:
            await self._repo.desmarcar_principal(data.producto_id, data.producto_unidad_id)
        await self._repo.crear(imagen)
        return imagen


# --------------------------------------------------------------------------- #
@dataclass
class ActualizarImagenInput:
    imagen_id: UUID
    producto_id: UUID | None = None          # dueño esperado, para validar pertenencia
    producto_unidad_id: UUID | None = None
    url: str | None = None
    alt_texto: str | None = None
    cambiar_alt_texto: bool = False
    orden: int | None = None
    es_principal: bool | None = None


class ActualizarImagenUseCase:
    def __init__(self, imagen_repo: ImagenRepository):
        self._repo = imagen_repo

    async def ejecutar(self, data: ActualizarImagenInput) -> ProductoImagen:
        imagen = await self._repo.obtener(data.imagen_id)
        if imagen is None or (
            imagen.producto_id != data.producto_id
            or imagen.producto_unidad_id != data.producto_unidad_id
        ):
            raise ImagenNoEncontrada(f"No existe la imagen {data.imagen_id} para ese dueño.")

        imagen.actualizar(
            url=data.url,
            alt_texto=data.alt_texto,
            cambiar_alt_texto=data.cambiar_alt_texto,
            orden=data.orden,
            es_principal=data.es_principal,
        )
        if data.es_principal:
            await self._repo.desmarcar_principal(
                imagen.producto_id, imagen.producto_unidad_id, excepto_id=imagen.id
            )
        await self._repo.actualizar(imagen)
        return imagen


# --------------------------------------------------------------------------- #
class EliminarImagenUseCase:
    def __init__(
        self, imagen_repo: ImagenRepository, almacen: AlmacenImagenes | None = None
    ):
        self._repo = imagen_repo
        self._almacen = almacen

    async def ejecutar(
        self, imagen_id: UUID,
        producto_id: UUID | None = None, producto_unidad_id: UUID | None = None,
    ) -> None:
        imagen = await self._repo.obtener(imagen_id)
        if imagen is None or (
            imagen.producto_id != producto_id or imagen.producto_unidad_id != producto_unidad_id
        ):
            raise ImagenNoEncontrada(f"No existe la imagen {imagen_id} para ese dueño.")
        await self._repo.eliminar(imagen_id)
        # Imagen propia (S3): borra también el original y su miniatura (best-effort).
        if self._almacen is not None and imagen.object_key:
            await self._almacen.eliminar(imagen.object_key)
            await self._almacen.eliminar(AlmacenImagenes.key_miniatura(imagen.object_key))
